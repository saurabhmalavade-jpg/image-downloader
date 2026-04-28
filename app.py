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
[data-testid="stHeader"] { background: transparent !important; }
#MainMenu, footer, [data-testid="stToolbar"] { display: none !important; }
.stats-row { display:flex; gap:1rem; margin-bottom:1.5rem; flex-wrap:wrap; }
.stat-box {
    flex:1; min-width:110px; background:#fff;
    border:1px solid #dde1ef; border-radius:10px;
    padding:1rem 1.2rem; text-align:center;
    box-shadow:0 1px 4px rgba(0,0,0,0.05);
}
.stat-num { font-size:2rem; font-weight:700; color:#4361ee; line-height:1; }
.stat-lbl { font-size:0.65rem; color:#888ea8; text-transform:uppercase;
            letter-spacing:0.08em; margin-top:0.3rem; font-weight:500; }
.sec-label { font-size:0.68rem; font-weight:600; letter-spacing:0.12em;
             text-transform:uppercase; color:#4361ee; margin-bottom:0.4rem; }
.stButton > button {
    background:#4361ee !important; color:#fff !important;
    font-weight:600 !important; font-size:1rem !important;
    border:none !important; border-radius:8px !important;
    padding:0.65rem 1.5rem !important; width:100% !important;
}
.stButton > button:hover    { background:#3a0ca3 !important; }
.stButton > button:disabled { background:#dde1ef !important; color:#aaa !important; }
[data-testid="stDownloadButton"] > button {
    background:#fff !important; color:#4361ee !important;
    border:2px solid #4361ee !important; font-weight:600 !important;
    border-radius:8px !important; width:100% !important; margin-top:0.4rem !important;
}
[data-testid="stDownloadButton"] > button:hover {
    background:#4361ee !important; color:#fff !important;
}
[data-testid="stProgress"] > div > div { background:#4361ee !important; }
[data-testid="stFileUploader"] {
    background:#fff !important; border:2px dashed #dde1ef !important; border-radius:10px !important;
}
.log-box {
    background:#f8f9fc; border:1px solid #dde1ef; border-radius:8px;
    padding:0.9rem 1rem; font-family:monospace; font-size:0.72rem;
    color:#555; max-height:220px; overflow-y:auto; line-height:1.9;
}
.log-ok  { color:#2ecc71; font-weight:600; }
.log-err { color:#e74c3c; font-weight:600; }
[data-testid="stDataFrame"] {
    background:#fff !important; border:1px solid #dde1ef !important; border-radius:10px !important;
}
details { border:1px solid #dde1ef !important; border-radius:8px !important; background:#fff !important; }
</style>
""", unsafe_allow_html=True)
# ── Helpers ───────────────────────────────────────────────────────────────────
def get_filename_from_url(url: str) -> str:
    parsed   = urlparse(url)
    filename = unquote(os.path.basename(parsed.path))
    if not filename:
        filename = unquote(url.strip('/').split('/')[-1].split('?')[0])
    return filename or "file"
def download_one(url: str, folder: str, store: dict, lock: threading.Lock):
    try:
        filename          = get_filename_from_url(url)
        base, ext         = os.path.splitext(filename)
        resp              = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        if not ext:
            ct  = resp.headers.get('content-type', '')
            ext = mimetypes.guess_extension(ct.split(';')[0]) or ''
            if ext:
                filename = f"{base}{ext}"
        with lock:
            key, n = f"{folder}/{filename}", 1
            while key in store:
                key = f"{folder}/{base}({n}){ext}"
                n  += 1
            store[key] = b""
        data = b"".join(resp.iter_content(8192))
        with lock:
            store[key] = data
        return True, key, None
    except Exception as e:
        return False, None, str(e)
def make_zip(store: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, data in store.items():
            if data:
                zf.writestr(path, data)
    buf.seek(0)
    return buf.read()
def make_report_excel(results: list) -> bytes:
    from collections import defaultdict, OrderedDict
    folder_data = OrderedDict()
    col_names_seen = []
    col_names_set  = set()
    for r in results:
        folder   = r["folder"]
        col_name = r.get("col_name", "URL")
        if folder not in folder_data:
            folder_data[folder] = {}
        folder_data[folder][col_name] = r
        if col_name not in col_names_set:
            col_names_seen.append(col_name)
            col_names_set.add(col_name)
    rows = []
    for folder, col_map in folder_data.items():
        row = {"Folder": folder}
        for col_name in col_names_seen:
            r = col_map.get(col_name)
            if r:
                row[col_name]                  = r["url"]
                row[f"{col_name} Status"]      = "✅ Success" if r["ok"] else "❌ Failed"
                row[f"{col_name} Saved As"]    = r.get("saved_as", "")
                if not r["ok"]:
                    row[f"{col_name} Error"]   = r.get("error", "")
            else:
                row[col_name]                  = ""
                row[f"{col_name} Status"]      = "—"
                row[f"{col_name} Saved As"]    = ""
        rows.append(row)
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    buf.seek(0)
    return buf.read()
def parse_tasks(df: pd.DataFrame) -> list:
    tasks      = []
    folder_col = df.columns[0]
    link_cols  = df.columns[1:]
    for _, row in df.iterrows():
        folder = str(row[folder_col]).strip()
        if not folder or folder.lower() == "nan":
            continue
        safe = "".join(c for c in folder if c.isalnum() or c in (' ', '_', '-')).strip()
        for col in link_cols:
            url = row[col]
            if isinstance(url, str) and url.strip().startswith(("http://", "https://")):
                tasks.append({
                    "folder":   safe,
                    "url":      url.strip(),
                    "filename": get_filename_from_url(url.strip()),
                    "col_name": str(col),
                })
    return tasks
# ── Session state ─────────────────────────────────────────────────────────────
for k, v in {
    "tasks":     [],
    "started":   False,
    "finished":  False,
    "results":   [],
    "zip_bytes": None,
    "log":       [],
}.items():
    if k not in st.session_state:
        st.session_state[k] = v
# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 🖼️ Image Downloader- OTTO")
st.markdown("Upload your Excel file → preview → download all images as a ZIP.")
st.divider()
left, right = st.columns([1, 1.7], gap="large")
# ══════════════════════════════════════════════════════════
# LEFT PANEL
# ══════════════════════════════════════════════════════════
with left:
    # ① Upload
    st.markdown('<div class="sec-label">① Upload Excel File</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("Excel", type=["xlsx", "xls"], label_visibility="collapsed")
    if uploaded:
        try:
            df = pd.read_excel(uploaded)
            if df.shape[1] < 2:
                st.error("Excel must have at least 2 columns.")
            else:
                tasks = parse_tasks(df)
                if tasks != st.session_state.tasks:
                    st.session_state.tasks    = tasks
                    st.session_state.started  = False
                    st.session_state.finished = False
                    st.session_state.results  = []
                    st.session_state.zip_bytes = None
                    st.session_state.log      = []
        except Exception as e:
            st.error(f"Could not read file: {e}")
    st.markdown("<br>", unsafe_allow_html=True)
    # ② Start button — only shown before download starts
    if not st.session_state.started:
        st.markdown('<div class="sec-label">② Start Download</div>', unsafe_allow_html=True)
        can_run = bool(st.session_state.tasks)
        if st.button("🚀  Start Downloading", disabled=not can_run):
            st.session_state.started  = True
            st.session_state.finished = False
            st.session_state.results  = []
            st.session_state.log      = []
            st.session_state.zip_bytes = None
            st.rerun()
    # ③ Download buttons — shown ONLY after finished
    if st.session_state.finished and st.session_state.zip_bytes:
        st.markdown('<div class="sec-label">③ Download Results</div>', unsafe_allow_html=True)
        st.success("✅ All done! Your files are ready.")
        st.download_button(
            label="⬇️  Download ZIP (all images)",
            data=st.session_state.zip_bytes,
            file_name="downloaded_images.zip",
            mime="application/zip",
            key="dl_zip",
        )
        if st.session_state.results:
            st.download_button(
                label="📊  Download Status Report (.xlsx)",
                data=make_report_excel(st.session_state.results),
                file_name="download_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_report",
            )
        # Reset button to allow new download
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄  Start New Download"):
            st.session_state.started   = False
            st.session_state.finished  = False
            st.session_state.results   = []
            st.session_state.zip_bytes = None
            st.session_state.log       = []
            st.session_state.tasks     = []
            st.rerun()
# ══════════════════════════════════════════════════════════
# RIGHT PANEL
# ══════════════════════════════════════════════════════════
with right:
    tasks = st.session_state.tasks
    # ── Preview (before start) ──
    if tasks and not st.session_state.started:
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
            pd.DataFrame([{"Folder": t["folder"], "Filename": t["filename"], "URL": t["url"]}
                          for t in tasks]),
            use_container_width=True, height=300, hide_index=True,
        )
    # ── DOWNLOAD IN PROGRESS — runs in this same script execution ──
    if st.session_state.started and not st.session_state.finished:
        total = len(tasks)
        st.markdown('<div class="sec-label">⬇ Downloading…</div>', unsafe_allow_html=True)
        prog_bar  = st.progress(0)
        prog_text = st.empty()
        log_area  = st.empty()
        store     = {}
        lock      = threading.Lock()
        results   = []
        completed = 0
        log_lines = []
        workers = min(16, (os.cpu_count() or 4) * 4)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            future_map = {ex.submit(download_one, t["url"], t["folder"], store, lock): t
                          for t in tasks}
            for future in concurrent.futures.as_completed(future_map):
                task         = future_map[future]
                ok, key, err = future.result()
                completed   += 1
                pct          = completed / total
                results.append({
                    "folder":   task["folder"],
                    "url":      task["url"],
                    "col_name": task.get("col_name", "URL"),
                    "saved_as": key.split("/", 1)[-1] if key else task["filename"],
                    "ok":       ok,
                    "error":    err or "",
                })
                prog_bar.progress(pct)
                prog_text.markdown(f"**{completed} / {total}** — {int(pct*100)}% complete")
                if ok:
                    log_lines.append(f'<span class="log-ok">✓</span>&nbsp; {task["folder"]}/{task["filename"]}')
                else:
                    log_lines.append(f'<span class="log-err">✗</span>&nbsp; {task["url"][:65]} — {err}')
                log_area.markdown(
                    f'<div class="log-box">{"<br>".join(log_lines[-14:])}</div>',
                    unsafe_allow_html=True,
                )
        # ── Build ZIP immediately in this same run ──
        prog_text.markdown("**📦 Packing ZIP…**")
        zip_bytes = make_zip(store)
        # Save everything to session state
        st.session_state.results   = results
        st.session_state.zip_bytes = zip_bytes
        st.session_state.finished  = True
        st.session_state.started   = False
        st.rerun()
    # ── Results summary (after finish) ──
    if st.session_state.finished and st.session_state.results:
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
            with st.expander(f"⚠️ {len(failed_items)} failed downloads"):
                for r in failed_items:
                    st.markdown(
                        f'`{r["url"][:80]}`  \n'
                        f'<span style="color:#e74c3c;font-size:0.8rem;">↳ {r["error"]}</span>',
                        unsafe_allow_html=True,
                    )
    # ── Empty state ──
    if not tasks and not st.session_state.started and not st.session_state.finished:
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

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.footer {
    position: fixed;
    bottom: 0;
    left: 0;
    width: 100%;
    background-color: #fff;
    color: #888ea8;
    text-align: center;
    padding: 10px 0;
    font-size: 0.75rem;
    border-top: 1px solid #dde1ef;
    font-family: 'Inter', sans-serif;
    font-weight: 500;
    letter-spacing: 0.03em;
    z-index: 999;
}
</style>
<div class="footer">
    © Designed and Developed by Saurabh Malavade
</div>
""", unsafe_allow_html=True)
