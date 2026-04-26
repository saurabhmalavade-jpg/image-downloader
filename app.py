import streamlit as st
import pandas as pd
import requests
import os
import zipfile
import io
import mimetypes
import concurrent.futures
import threading
import time
from urllib.parse import urlparse, unquote

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Image Downloader",
    page_icon="🖼️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;800&display=swap');

/* ── Root theme ── */
:root {
    --bg:       #0d0d0d;
    --surface:  #161616;
    --border:   #2a2a2a;
    --accent:   #c8ff00;
    --accent2:  #ff6b35;
    --text:     #f0f0f0;
    --muted:    #666;
    --success:  #39ff8a;
    --error:    #ff4545;
    --warning:  #ffcc00;
}

html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'Syne', sans-serif;
}

[data-testid="stHeader"] { background: transparent !important; }

/* ── Hide default streamlit chrome ── */
#MainMenu, footer, [data-testid="stToolbar"] { display: none !important; }

/* ── Hero header ── */
.hero {
    padding: 2.5rem 0 1.5rem 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 2rem;
}
.hero-title {
    font-size: clamp(2.4rem, 5vw, 4rem);
    font-weight: 800;
    letter-spacing: -0.03em;
    line-height: 1;
    margin: 0;
}
.hero-title span { color: var(--accent); }
.hero-sub {
    font-family: 'Space Mono', monospace;
    font-size: 0.78rem;
    color: var(--muted);
    margin-top: 0.5rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

/* ── Cards ── */
.card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1.2rem;
}
.card-label {
    font-family: 'Space Mono', monospace;
    font-size: 0.65rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 0.6rem;
}

/* ── Stat boxes ── */
.stats-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
}
.stat-box {
    flex: 1;
    min-width: 120px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1rem 1.2rem;
    text-align: center;
}
.stat-box .num {
    font-size: 2rem;
    font-weight: 800;
    line-height: 1;
}
.stat-box .lbl {
    font-family: 'Space Mono', monospace;
    font-size: 0.6rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-top: 0.3rem;
}
.num-green  { color: var(--success); }
.num-red    { color: var(--error); }
.num-yellow { color: var(--warning); }
.num-accent { color: var(--accent); }

/* ── File uploader override ── */
[data-testid="stFileUploader"] {
    background: var(--surface) !important;
    border: 1.5px dashed var(--border) !important;
    border-radius: 12px !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: var(--accent) !important;
}

/* ── Buttons ── */
.stButton > button {
    background: var(--accent) !important;
    color: #000 !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.7rem 2rem !important;
    width: 100%;
    transition: opacity 0.15s;
}
.stButton > button:hover { opacity: 0.85 !important; }
.stButton > button:disabled {
    background: var(--border) !important;
    color: var(--muted) !important;
}

/* ── Slider ── */
[data-testid="stSlider"] .stSlider > div { color: var(--accent) !important; }

/* ── Progress bar ── */
[data-testid="stProgress"] > div > div {
    background: var(--accent) !important;
}

/* ── Table / dataframe ── */
[data-testid="stDataFrame"] {
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}

/* ── Status pills ── */
.pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    font-weight: 700;
}
.pill-success { background: #0f2a1a; color: var(--success); border: 1px solid var(--success); }
.pill-fail    { background: #2a0f0f; color: var(--error);   border: 1px solid var(--error); }
.pill-pending { background: #1a1a0f; color: var(--warning); border: 1px solid var(--warning); }

/* ── Log box ── */
.log-box {
    background: #0a0a0a;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem;
    font-family: 'Space Mono', monospace;
    font-size: 0.72rem;
    color: var(--muted);
    max-height: 200px;
    overflow-y: auto;
    line-height: 1.7;
}
.log-ok  { color: var(--success); }
.log-err { color: var(--error); }
.log-inf { color: var(--accent); }

/* ── Download button override ── */
[data-testid="stDownloadButton"] > button {
    background: transparent !important;
    color: var(--accent) !important;
    border: 1.5px solid var(--accent) !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    width: 100%;
}
[data-testid="stDownloadButton"] > button:hover {
    background: var(--accent) !important;
    color: #000 !important;
}

/* ── Divider ── */
hr { border-color: var(--border) !important; margin: 1.5rem 0 !important; }

/* ── Select / number input ── */
[data-testid="stNumberInput"] input,
[data-testid="stSelectbox"] select {
    background: var(--surface) !important;
    color: var(--text) !important;
    border-color: var(--border) !important;
    font-family: 'Space Mono', monospace !important;
}

/* ── Expander ── */
details {
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    background: var(--surface) !important;
}
</style>
""", unsafe_allow_html=True)


# ── Helper functions ───────────────────────────────────────────────────────────

def get_filename_from_url(url: str) -> str:
    """Extract and URL-decode exact filename from URL."""
    parsed = urlparse(url)
    filename = unquote(os.path.basename(parsed.path))
    if not filename:
        filename = unquote(url.strip('/').split('/')[-1].split('?')[0])
    return filename


def download_file(url: str, folder_name: str, in_memory_store: dict, lock: threading.Lock):
    """
    Download a single file into memory (bytes), storing it in in_memory_store.
    Key: folder_name/filename
    """
    try:
        parsed = urlparse(url)
        filename = unquote(os.path.basename(parsed.path))
        if not filename:
            filename = unquote(url.strip('/').split('/')[-1].split('?')[0])

        base_name, extension = os.path.splitext(filename)

        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        # Guess extension from Content-Type if missing
        if not extension:
            content_type = response.headers.get('content-type', '')
            guessed = mimetypes.guess_extension(content_type.split(';')[0])
            if guessed:
                extension = guessed
                filename = f"{base_name}{extension}"

        # Handle duplicates within the same folder
        with lock:
            key = f"{folder_name}/{filename}"
            counter = 1
            original_key = key
            while key in in_memory_store:
                key = f"{folder_name}/{base_name}({counter}){extension}"
                counter += 1
            in_memory_store[key] = b""   # reserve slot

        # Download bytes
        content = b"".join(response.iter_content(chunk_size=8192))

        with lock:
            in_memory_store[key] = content

        return True, key, None

    except Exception as e:
        return False, None, str(e)


def build_zip(in_memory_store: dict) -> bytes:
    """Pack all downloaded files into a ZIP archive in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, data in in_memory_store.items():
            if data:
                zf.writestr(path, data)
    buf.seek(0)
    return buf.read()


def parse_excel(file) -> tuple[pd.DataFrame | None, str]:
    """Read and validate the uploaded Excel file."""
    try:
        df = pd.read_excel(file)
        if df.empty or df.shape[1] < 2:
            return None, "Excel must have at least 2 columns: folder names + image URLs."
        return df, ""
    except Exception as e:
        return None, str(e)


# ── Session state init ─────────────────────────────────────────────────────────
for key, default in {
    "df": None,
    "tasks": [],
    "results": [],
    "zip_bytes": None,
    "running": False,
    "done": False,
    "log": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Hero ───────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <p class="hero-title">Image<span>.</span>Downloader</p>
  <p class="hero-sub">Upload → Preview → Download → Get ZIP</p>
</div>
""", unsafe_allow_html=True)


# ── Layout: two columns ────────────────────────────────────────────────────────
left, right = st.columns([1, 1.6], gap="large")


# ══════════════════════════════════════════════════════════════════════════════
# LEFT PANEL — Controls
# ══════════════════════════════════════════════════════════════════════════════
with left:

    # ── Step 1: Upload ──
    st.markdown('<div class="card-label">① Upload Excel File</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader(
        label="Excel file",
        type=["xlsx", "xls"],
        label_visibility="collapsed",
    )

    if uploaded:
        df, err = parse_excel(uploaded)
        if err:
            st.error(f"❌ {err}")
            st.session_state.df = None
            st.session_state.tasks = []
        else:
            st.session_state.df = df

            # Build task list
            tasks = []
            folder_col = df.columns[0]
            link_cols  = df.columns[1:]
            for _, row in df.iterrows():
                folder = str(row[folder_col]).strip()
                if not folder or folder == "nan":
                    continue
                # Sanitize folder name
                safe_folder = "".join(
                    c for c in folder if c.isalnum() or c in (' ', '_', '-')
                ).strip()
                for col in link_cols:
                    url = row[col]
                    if isinstance(url, str) and url.strip().startswith(("http://", "https://")):
                        tasks.append({
                            "folder": safe_folder,
                            "url": url.strip(),
                            "filename": get_filename_from_url(url.strip()),
                            "col": col,
                        })
            st.session_state.tasks = tasks
            st.session_state.done = False
            st.session_state.zip_bytes = None
            st.session_state.results = []
            st.session_state.log = []

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 2: Settings ──
    st.markdown('<div class="card-label">② Settings</div>', unsafe_allow_html=True)

    workers = st.slider(
        "Concurrent download workers",
        min_value=1, max_value=16, value=4, step=1,
        help="More workers = faster downloads, but uses more bandwidth."
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 3: Run ──
    st.markdown('<div class="card-label">③ Run</div>', unsafe_allow_html=True)

    can_run = bool(st.session_state.tasks) and not st.session_state.running

    if st.button(
        "🚀  Start Downloading" if can_run else
        ("⏳  Downloading..." if st.session_state.running else "Upload a file first"),
        disabled=not can_run,
    ):
        st.session_state.running = True
        st.session_state.done    = False
        st.session_state.results = []
        st.session_state.log     = []
        st.session_state.zip_bytes = None
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 4: Download ZIP ──
    st.markdown('<div class="card-label">④ Download Results</div>', unsafe_allow_html=True)

    if st.session_state.zip_bytes:
        st.download_button(
            label="⬇️  Download ZIP",
            data=st.session_state.zip_bytes,
            file_name="downloaded_images.zip",
            mime="application/zip",
        )

        # ── Status report download ──
        if st.session_state.results:
            rows = []
            for r in st.session_state.results:
                rows.append({
                    "Folder":   r["folder"],
                    "URL":      r["url"],
                    "Filename": r.get("filename", ""),
                    "Status":   "Success" if r["ok"] else "Failed",
                    "Error":    r.get("error", ""),
                })
            report_df = pd.DataFrame(rows)
            buf = io.BytesIO()
            report_df.to_excel(buf, index=False)
            buf.seek(0)
            st.download_button(
                label="📊  Download Status Report (.xlsx)",
                data=buf.read(),
                file_name="download_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    elif not st.session_state.tasks:
        st.markdown(
            '<p style="color:var(--muted);font-family:\'Space Mono\',monospace;font-size:0.75rem;">'
            'Upload a file to enable downloads.</p>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<p style="color:var(--muted);font-family:\'Space Mono\',monospace;font-size:0.75rem;">'
            'Run the downloader first.</p>',
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# RIGHT PANEL — Preview & Progress
# ══════════════════════════════════════════════════════════════════════════════
with right:

    # ── Preview table ──
    if st.session_state.tasks:
        tasks = st.session_state.tasks

        # Stats row
        total_tasks   = len(tasks)
        folders_found = len(set(t["folder"] for t in tasks))

        st.markdown(f"""
        <div class="stats-row">
          <div class="stat-box">
            <div class="num num-accent">{total_tasks}</div>
            <div class="lbl">Images</div>
          </div>
          <div class="stat-box">
            <div class="num num-accent">{folders_found}</div>
            <div class="lbl">Folders</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Preview dataframe
        st.markdown('<div class="card-label">Preview — Tasks Queued</div>', unsafe_allow_html=True)
        preview_df = pd.DataFrame([
            {"Folder": t["folder"], "Filename": t["filename"], "URL": t["url"]}
            for t in tasks
        ])
        st.dataframe(preview_df, use_container_width=True, height=220, hide_index=True)

    # ── Active download progress ──
    if st.session_state.running:
        tasks = st.session_state.tasks
        total = len(tasks)

        st.markdown('<div class="card-label">⬇ Download Progress</div>', unsafe_allow_html=True)
        prog_bar  = st.progress(0)
        prog_text = st.empty()
        log_area  = st.empty()

        in_memory_store: dict = {}
        lock = threading.Lock()
        results = []
        completed = 0
        log_lines = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {
                executor.submit(download_file, t["url"], t["folder"], in_memory_store, lock): t
                for t in tasks
            }

            for future in concurrent.futures.as_completed(future_map):
                task = future_map[future]
                ok, key, err = future.result()
                completed += 1

                results.append({
                    "folder":   task["folder"],
                    "url":      task["url"],
                    "filename": key.split("/", 1)[-1] if key else task["filename"],
                    "ok":       ok,
                    "error":    err or "",
                })

                pct = completed / total
                prog_bar.progress(pct)
                prog_text.markdown(
                    f'<p style="font-family:\'Space Mono\',monospace;font-size:0.75rem;color:var(--muted);">'
                    f'{completed} / {total} &nbsp;·&nbsp; {int(pct*100)}%</p>',
                    unsafe_allow_html=True,
                )

                if ok:
                    log_lines.append(f'<span class="log-ok">✓</span>  {task["folder"]}/{task["filename"]}')
                else:
                    log_lines.append(f'<span class="log-err">✗</span>  {task["url"][:60]}… — {err}')

                log_area.markdown(
                    f'<div class="log-box">{"<br>".join(log_lines[-12:])}</div>',
                    unsafe_allow_html=True,
                )

        # Build ZIP
        prog_text.markdown(
            '<p style="font-family:\'Space Mono\',monospace;font-size:0.75rem;color:var(--accent);">'
            'Packing ZIP…</p>',
            unsafe_allow_html=True,
        )
        zip_bytes = build_zip(in_memory_store)

        st.session_state.results   = results
        st.session_state.zip_bytes = zip_bytes
        st.session_state.running   = False
        st.session_state.done      = True
        st.session_state.log       = log_lines
        st.rerun()

    # ── Results summary after completion ──
    if st.session_state.done and st.session_state.results:
        results = st.session_state.results
        total   = len(results)
        success = sum(1 for r in results if r["ok"])
        failed  = total - success

        st.markdown(f"""
        <div class="stats-row">
          <div class="stat-box">
            <div class="num num-green">{success}</div>
            <div class="lbl">Success</div>
          </div>
          <div class="stat-box">
            <div class="num num-red">{failed}</div>
            <div class="lbl">Failed</div>
          </div>
          <div class="stat-box">
            <div class="num num-accent">{total}</div>
            <div class="lbl">Total</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Log
        if st.session_state.log:
            st.markdown('<div class="card-label">Activity Log</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="log-box">{"<br>".join(st.session_state.log)}</div>',
                unsafe_allow_html=True,
            )

        # Failed list
        failed_items = [r for r in results if not r["ok"]]
        if failed_items:
            with st.expander(f"⚠️  {len(failed_items)} failed downloads"):
                for r in failed_items:
                    st.markdown(
                        f'<span style="font-family:Space Mono,monospace;font-size:0.72rem;">'
                        f'<span style="color:var(--error)">✗</span> '
                        f'<code>{r["url"][:80]}</code><br>'
                        f'<span style="color:var(--muted)">  {r["error"]}</span></span>',
                        unsafe_allow_html=True,
                    )

    # ── Empty state ──
    if not st.session_state.tasks and not st.session_state.running:
        st.markdown("""
        <div style="
            border: 1.5px dashed #2a2a2a;
            border-radius: 12px;
            padding: 3rem 2rem;
            text-align: center;
            margin-top: 1rem;
        ">
          <div style="font-size:3rem;margin-bottom:1rem;">🖼️</div>
          <p style="font-family:'Syne',sans-serif;font-weight:600;font-size:1.1rem;margin:0;">
            Upload an Excel file to get started
          </p>
          <p style="font-family:'Space Mono',monospace;font-size:0.7rem;color:#555;margin-top:0.5rem;">
            Column A → folder names &nbsp;|&nbsp; Columns B+ → image URLs
          </p>
        </div>
        """, unsafe_allow_html=True)
