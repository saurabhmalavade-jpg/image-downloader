import streamlit as st
import pandas as pd
import requests
import os
import zipfile
import io
import mimetypes
import concurrent.futures
import threading
from urllib.parse import urlparse, unquote

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Image Downloader",
    page_icon="🖼️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Light theme CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="block-container"] {
    background-color: #f4f6fb !important;
    color: #1a1a2e !important;
    font-family: 'Inter', sans-serif !important;
}

[data-testid="stHeader"]               { background: transparent !important; }
#MainMenu, footer, [data-testid="stToolbar"] { display: none !important; }

/* ── Stat boxes ── */
.stats-row {
    display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap;
}
.stat-box {
    flex: 1; min-width: 110px;
    background: #fff;
    border: 1px solid #dde1ef;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    text-align: center;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
.stat-num { font-size: 2rem; font-weight: 700; color: #4361ee; line-height: 1; }
.stat-lbl { font-size: 0.65rem; color: #888ea8; text-transform: uppercase;
            letter-spacing: 0.08em; margin-top: 0.3rem; font-weight: 500; }

/* ── Section labels ── */
.sec-label {
    font-size: 0.68rem; font-weight: 600; letter-spacing: 0.12em;
    text-transform: uppercase; color: #4361ee; margin-bottom: 0.4rem;
}

/* ── Buttons ── */
.stButton > button {
    background: #4361ee !important; color: #fff !important;
    font-weight: 600 !important; font-size: 1rem !important;
    border: none !important; border-radius: 8px !important;
    padding: 0.65rem 1.5rem !important; width: 100% !important;
}
.stButton > button:hover     { background: #3a0ca3 !important; }
.stButton > button:disabled  { background: #dde1ef !important; color: #aaa !important; }

/* ── Download buttons ── */
[data-testid="stDownloadButton"] > button {
    background: #fff !important; color: #4361ee !important;
    border: 2px solid #4361ee !important;
    font-weight: 600 !important; border-radius: 8px !important;
    width: 100% !important; margin-top: 0.4rem !important;
}
[data-testid="stDownloadButton"] > button:hover {
    background: #4361ee !important; color: #fff !important;
}

/* ── Progress bar ── */
[data-testid="stProgress"] > div > div { background: #4361ee !important; }

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: #fff !important;
    border: 2px dashed #dde1ef !important;
    border-radius: 10px !important;
}

/* ── Log box ── */
.log-box {
    background: #f8f9fc; border: 1px solid #dde1ef; border-radius: 8px;
    padding: 0.9rem 1rem; font-family: monospace; font-size: 0.72rem;
    color: #555; max-height: 200px; overflow-y: auto; line-height: 1.9;
}
.log-ok  { color: #2ecc71; font-weight: 600; }
.log-err { color: #e74c3c; font-weight: 600; }

/* ── Dataframe ── */
[data-testid="stDataFrame"] {
    background: #fff !important;
    border: 1px solid #dde1ef !important;
    border-radius: 10px !important;
}

/* ── Expander ── */
details { border: 1px solid #dde1ef !important; border-radius: 8px !important; background: #fff !important; }
</style>
""", unsafe_allow_html=True)


# ── Helper functions ───────────────────────────────────────────────────────────

def get_filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    filename = unquote(os.path.basename(parsed.path))
    if not filename:
        filename = unquote(url.strip('/').split('/')[-1].split('?')[0])
    return filename


def download_file(url: str, folder_name: str, in_memory_store: dict, lock: threading.Lock):
    """Download one file into memory. Stores bytes keyed by folder/filename."""
    try:
        parsed   = urlparse(url)
        filename = unquote(os.path.basename(parsed.path))
        if not filename:
            filename = unquote(url.strip('/').split('/')[-1].split('?')[0])

        base_name, extension = os.path.splitext(filename)

        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        # Guess extension from Content-Type if URL has none
        if not extension:
            content_type = response.headers.get('content-type', '')
            guessed = mimetypes.guess_extension(content_type.split(';')[0])
            if guessed:
                extension = guessed
                filename  = f"{base_name}{extension}"

        # Reserve a unique key (handle duplicate filenames in same folder)
        with lock:
            key     = f"{folder_name}/{filename}"
            counter = 1
            while key in in_memory_store:
                key = f"{folder_name}/{base_name}({counter}){extension}"
                counter += 1
            in_memory_store[key] = b""  # reserve slot

        content = b"".join(response.iter_content(chunk_size=8192))

        with lock:
            in_memory_store[key] = content

        return True, key, None

    except Exception as e:
        return False, None, str(e)


def build_zip(in_memory_store: dict) -> bytes:
    """Pack all downloaded files into a ZIP in memory and return bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, data in in_memory_store.items():
            if data:
                zf.writestr(path, data)
    buf.seek(0)
    return buf.read()


def parse_excel(file) -> tuple:
    try:
        df = pd.read_excel(file)
        if df.empty or df.shape[1] < 2:
            return None, "Excel must have at least 2 columns: folder names + image URLs."
        return df, ""
    except Exception as e:
        return None, str(e)


# ── Session state ──────────────────────────────────────────────────────────────
for key, default in {
    "df":        None,
    "tasks":     [],
    "results":   [],
    "zip_bytes": None,
    "running":   False,
    "done":      False,
    "log":       [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 🖼️ Image Downloader")
st.markdown("Upload your Excel file → preview tasks → download all images as a ZIP.")
st.divider()

# ── Two column layout ─────────────────────────────────────────────────────────
left, right = st.columns([1, 1.7], gap="large")


# ══════════════════════════════════════════════════════════
# LEFT — Upload + Run + Download
# ══════════════════════════════════════════════════════════
with left:

    # ── Upload ──
    st.markdown('<div class="sec-label">① Upload Excel File</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader(
        label="Excel",
        type=["xlsx", "xls"],
        label_visibility="collapsed",
    )

    if uploaded:
        df, err = parse_excel(uploaded)
        if err:
            st.error(f"❌ {err}")
            st.session_state.df    = None
            st.session_state.tasks = []
        else:
            st.session_state.df = df

            # Build task list from the Excel
            tasks      = []
            folder_col = df.columns[0]
            link_cols  = df.columns[1:]

            for _, row in df.iterrows():
                folder = str(row[folder_col]).strip()
                if not folder or folder.lower() == "nan":
                    continue
                safe_folder = "".join(
                    c for c in folder if c.isalnum() or c in (' ', '_', '-')
                ).strip()
                for col in link_cols:
                    url = row[col]
                    if isinstance(url, str) and url.strip().startswith(("http://", "https://")):
                        tasks.append({
                            "folder":   safe_folder,
                            "url":      url.strip(),
                            "filename": get_filename_from_url(url.strip()),
                        })

            st.session_state.tasks     = tasks
            st.session_state.done      = False
            st.session_state.zip_bytes = None
            st.session_state.results   = []
            st.session_state.log       = []

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Run ──
    st.markdown('<div class="sec-label">② Start Download</div>', unsafe_allow_html=True)

    can_run = bool(st.session_state.tasks) and not st.session_state.running

    if st.button(
        "🚀  Start Downloading" if not st.session_state.running else "⏳  Downloading...",
        disabled=not can_run,
    ):
        st.session_state.running   = True
        st.session_state.done      = False
        st.session_state.results   = []
        st.session_state.log       = []
        st.session_state.zip_bytes = None
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Download results ──
    st.markdown('<div class="sec-label">③ Download Results</div>', unsafe_allow_html=True)

    if st.session_state.zip_bytes:
        # ── ZIP ──
        st.success("✅ Download ready!")
        st.download_button(
            label="⬇️  Download ZIP (all images)",
            data=st.session_state.zip_bytes,
            file_name="downloaded_images.zip",
            mime="application/zip",
            key="zip_download",
        )

        # ── Excel status report ──
        if st.session_state.results:
            rows = [
                {
                    "Folder":   r["folder"],
                    "Filename": r.get("saved_as", ""),
                    "URL":      r["url"],
                    "Status":   "Success" if r["ok"] else "Failed",
                    "Error":    r.get("error", ""),
                }
                for r in st.session_state.results
            ]
            buf = io.BytesIO()
            pd.DataFrame(rows).to_excel(buf, index=False)
            buf.seek(0)
            st.download_button(
                label="📊  Download Status Report (.xlsx)",
                data=buf.read(),
                file_name="download_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="report_download",
            )

    elif st.session_state.running:
        st.info("⏳ Downloading in progress…")
    else:
        st.caption("Run the downloader first to enable downloads.")


# ══════════════════════════════════════════════════════════
# RIGHT — Preview + Progress + Results
# ══════════════════════════════════════════════════════════
with right:

    # ── Preview ──
    if st.session_state.tasks and not st.session_state.running:
        tasks = st.session_state.tasks

        st.markdown(f"""
        <div class="stats-row">
          <div class="stat-box">
            <div class="stat-num">{len(tasks)}</div>
            <div class="stat-lbl">Images</div>
          </div>
          <div class="stat-box">
            <div class="stat-num">{len(set(t["folder"] for t in tasks))}</div>
            <div class="stat-lbl">Folders</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="sec-label">Preview — Tasks Queued</div>', unsafe_allow_html=True)
        st.dataframe(
            pd.DataFrame([{"Folder": t["folder"], "Filename": t["filename"], "URL": t["url"]} for t in tasks]),
            use_container_width=True,
            height=300,
            hide_index=True,
        )

    # ── Active downloading ──
    if st.session_state.running:
        tasks = st.session_state.tasks
        total = len(tasks)

        st.markdown('<div class="sec-label">⬇ Downloading…</div>', unsafe_allow_html=True)
        prog_bar  = st.progress(0)
        prog_text = st.empty()
        log_area  = st.empty()

        in_memory_store: dict = {}
        lock      = threading.Lock()
        results   = []
        completed = 0
        log_lines = []

        # Auto worker count — use CPU count x 4, capped at 16
        auto_workers = min(16, (os.cpu_count() or 4) * 4)

        with concurrent.futures.ThreadPoolExecutor(max_workers=auto_workers) as executor:
            future_map = {
                executor.submit(download_file, t["url"], t["folder"], in_memory_store, lock): t
                for t in tasks
            }
            for future in concurrent.futures.as_completed(future_map):
                task              = future_map[future]
                ok, key, err      = future.result()
                completed        += 1
                pct               = completed / total

                results.append({
                    "folder":   task["folder"],
                    "url":      task["url"],
                    "saved_as": key.split("/", 1)[-1] if key else task["filename"],
                    "ok":       ok,
                    "error":    err or "",
                })

                prog_bar.progress(pct)
                prog_text.markdown(
                    f"**{completed} / {total}** &nbsp;·&nbsp; {int(pct * 100)}% complete"
                )

                if ok:
                    log_lines.append(f'<span class="log-ok">✓</span>&nbsp; {task["folder"]}/{task["filename"]}')
                else:
                    log_lines.append(f'<span class="log-err">✗</span>&nbsp; {task["url"][:70]} — {err}')

                log_area.markdown(
                    f'<div class="log-box">{"<br>".join(log_lines[-14:])}</div>',
                    unsafe_allow_html=True,
                )

        # All done — build ZIP and store in session state
        prog_text.markdown("**Packing ZIP file…**")
        zip_bytes = build_zip(in_memory_store)

        st.session_state.results   = results
        st.session_state.zip_bytes = zip_bytes
        st.session_state.running   = False
        st.session_state.done      = True
        st.session_state.log       = log_lines
        st.rerun()   # rerun so download buttons become active

    # ── Results summary ──
    if st.session_state.done and st.session_state.results:
        results = st.session_state.results
        success = sum(1 for r in results if r["ok"])
        failed  = len(results) - success

        st.markdown(f"""
        <div class="stats-row">
          <div class="stat-box">
            <div class="stat-num" style="color:#2ecc71">{success}</div>
            <div class="stat-lbl">Succeeded</div>
          </div>
          <div class="stat-box">
            <div class="stat-num" style="color:#e74c3c">{failed}</div>
            <div class="stat-lbl">Failed</div>
          </div>
          <div class="stat-box">
            <div class="stat-num">{len(results)}</div>
            <div class="stat-lbl">Total</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.log:
            st.markdown('<div class="sec-label">Activity Log</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="log-box">{"<br>".join(st.session_state.log)}</div>',
                unsafe_allow_html=True,
            )

        failed_items = [r for r in results if not r["ok"]]
        if failed_items:
            with st.expander(f"⚠️ {len(failed_items)} failed downloads — click to see details"):
                for r in failed_items:
                    st.markdown(
                        f'`{r["url"][:80]}`  \n'
                        f'<span style="color:#e74c3c;font-size:0.8rem;">Error: {r["error"]}</span>',
                        unsafe_allow_html=True,
                    )

    # ── Empty state ──
    if not st.session_state.tasks and not st.session_state.running and not st.session_state.done:
        st.markdown("""
        <div style="border:2px dashed #dde1ef; border-radius:12px; padding:3rem 2rem;
                    text-align:center; background:#fff; margin-top:1rem;">
          <div style="font-size:2.5rem; margin-bottom:0.8rem;">🖼️</div>
          <p style="font-weight:600; font-size:1.05rem; margin:0; color:#1a1a2e;">
            Upload an Excel file to get started
          </p>
          <p style="font-size:0.78rem; color:#888ea8; margin-top:0.5rem;">
            Column A → folder names &nbsp;|&nbsp; Columns B onwards → image URLs
          </p>
        </div>
        """, unsafe_allow_html=True)
