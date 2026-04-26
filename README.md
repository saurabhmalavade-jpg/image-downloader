# 🖼️ Image Downloader

A fast, browser-based image downloader with a clean UI built with **Streamlit**.

Upload an Excel file → preview tasks → download all images as a ZIP — no installation needed when deployed on Streamlit Cloud.

---

## ✨ Features

- 📂 **Folder-based downloads** — Column A = folder names, Columns B+ = image URLs
- 🚀 **Concurrent downloads** — adjustable worker count (1–16)
- 🗜️ **ZIP output** — all folders and images packed into one ZIP file
- 📊 **Status report** — downloadable Excel report showing Success/Failed per image
- 🔁 **Duplicate handling** — files with the same name get `(1)`, `(2)` suffixes
- 🔍 **Live progress log** — real-time activity feed during download
- 🌐 **URL-decoded filenames** — saves images with their exact original names

---

## 🚀 Deploy on Streamlit Cloud (Free)

### 1. Fork / Push to GitHub

Push this repo to your GitHub account.

### 2. Go to Streamlit Cloud

Visit [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.

### 3. Create a new app

- **Repository**: `your-username/image-downloader`
- **Branch**: `main`
- **Main file path**: `app.py`

Click **Deploy** — it goes live in ~1 minute. ✅

---

## 💻 Run Locally

```bash
# 1. Clone the repo
git clone https://github.com/your-username/image-downloader.git
cd image-downloader

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

Then open **http://localhost:8501** in your browser.

---

## 📋 Excel File Format

| FolderName   | URL_1                              | URL_2                              |
|--------------|------------------------------------|------------------------------------|
| Products     | https://example.com/img/photo.jpg  | https://example.com/img/photo2.jpg |
| Banners      | https://example.com/img/banner.png |                                    |

- **Column A** — folder name (letters, numbers, spaces, `_`, `-` only)
- **Columns B onwards** — image URLs (one per cell, `http://` or `https://`)
- Empty cells are safely skipped

---

## 🗂️ Project Structure

```
image-downloader/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

---

## 🛠️ Tech Stack

- [Streamlit](https://streamlit.io) — UI framework
- [Pandas](https://pandas.pydata.org) — Excel parsing
- [Requests](https://requests.readthedocs.io) — HTTP downloads
- [concurrent.futures](https://docs.python.org/3/library/concurrent.futures.html) — parallel downloads
