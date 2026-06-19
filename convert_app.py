"""
File Markdown Tool — Good Air Inc.
Two tools in one app, hosted on Streamlit Community Cloud:
  1. Convert documents to lightweight Markdown (saves Claude usage).
  2. Split or compress big plan sets into upload-ready pieces for Claude.
"""

import io
import os
import time
import shutil
import tempfile
import zipfile
import hashlib
import subprocess
from datetime import datetime, timedelta

import streamlit as st
import extra_streamlit_components as stx
from markitdown import MarkItDown
from pypdf import PdfReader, PdfWriter

LOGO = "goodair_logo.png"  # upload this file to the repo with EXACTLY this name

# Claude's upload limits for a chat PDF
LIMIT_PAGES = 100
LIMIT_MB = 30

st.set_page_config(page_title="File Markdown Tool", page_icon="❄️", layout="centered")

cookie_manager = stx.CookieManager()


def show_logo():
    if os.path.exists(LOGO):
        st.image(LOGO, width=280)


def token_for(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


# ---- Sign-in with optional "stay signed in" --------------------------------
def check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True

    secret = st.secrets.get("app_password", "")
    saved = cookie_manager.get("fmt_auth")
    if saved and secret and saved == token_for(secret):
        st.session_state["authenticated"] = True
        return True

    show_logo()
    st.title("File Markdown Tool")
    with st.form("login"):
        pw = st.text_input("Team password", type="password")
        remember = st.checkbox("Keep me signed in on this device", value=True)
        submitted = st.form_submit_button("Sign in")

    if submitted:
        if pw == secret:
            st.session_state["authenticated"] = True
            if remember:
                cookie_manager.set("fmt_auth", token_for(pw),
                                   expires_at=datetime.now() + timedelta(days=30))
                time.sleep(0.5)
            st.rerun()
        else:
            st.error("Incorrect password — try again.")
    return False


if not check_password():
    st.stop()
# ---------------------------------------------------------------------------


with st.sidebar:
    if st.button("Sign out"):
        try:
            cookie_manager.delete("fmt_auth")
        except Exception:
            pass
        st.session_state.clear()
        time.sleep(0.3)
        st.rerun()


# ---- PDF helpers -----------------------------------------------------------
def pdf_for_pages(reader, indices):
    writer = PdfWriter()
    for i in indices:
        writer.add_page(reader.pages[i])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def parse_ranges(text, max_pages):
    indices = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if "-" in part:
                a, b = part.split("-", 1)
                indices.extend(range(int(a) - 1, int(b)))
            else:
                indices.append(int(part) - 1)
        except ValueError:
            return None
    return [i for i in indices if 0 <= i < max_pages]


def show_limit_status(num_pages, size_bytes):
    mb = size_bytes / 1_000_000
    problems = []
    if num_pages > LIMIT_PAGES:
        problems.append(f"{num_pages} pages (max {LIMIT_PAGES})")
    if mb > LIMIT_MB:
        problems.append(f"{mb:.1f} MB (max {LIMIT_MB})")
    if problems:
        st.warning("⚠️ Over Claude's upload limit — " + " and ".join(problems)
                   + ". Claude will reject this. Pull fewer pages, or compress it below.")
    else:
        st.success(f"✅ Within Claude's limits ({num_pages} pages, {mb:.1f} MB) — ready to upload.")


# Ghostscript compression
QUALITY = {
    "Light — 300 dpi (best detail, biggest file)": "/printer",
    "Medium — 150 dpi (good balance)": "/ebook",
    "Strong — 72 dpi (smallest, blurriest)": "/screen",
}


def has_gs():
    return shutil.which("gs") is not None


def compress_pdf(data_bytes, setting):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as fin:
        fin.write(data_bytes)
        in_path = fin.name
    out_path = in_path[:-4] + "_c.pdf"
    try:
        subprocess.run(
            ["gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
             f"-dPDFSETTINGS={setting}", "-dNOPAUSE", "-dQUIET", "-dBATCH",
             f"-sOutputFile={out_path}", in_path],
            check=True,
        )
        with open(out_path, "rb") as f:
            return f.read()
    finally:
        for p in (in_path, out_path):
            try:
                os.unlink(p)
            except OSError:
                pass


def quality_picker(key):
    return st.selectbox(
        "Compression level", list(QUALITY.keys()), index=1, key=key,
        help="Higher dpi keeps more drawing detail but a larger file. "
             "Always double-check critical dimensions after compressing.",
    )
# ---------------------------------------------------------------------------


show_logo()
st.title("File Markdown Tool")

tab1, tab2 = st.tabs(["📄 Convert to Markdown", "✂️ Split or compress a plan set"])


# ===== TAB 1: Convert documents to Markdown =================================
with tab1:
    st.write(
        "Drop in PDFs, Word, Excel, or PowerPoint files. You'll get back lightweight text "
        "(Markdown) you can copy or download to attach to Claude instead of the heavy original."
    )

    converter = MarkItDown()
    uploaded = st.file_uploader(
        "Drag files here, or click to browse",
        type=["pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls", "csv", "html", "htm", "txt"],
        accept_multiple_files=True, key="md_files",
    )

    if uploaded:
        results = []
        for f in uploaded:
            suffix = os.path.splitext(f.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(f.getvalue())
                tmp_path = tmp.name
            text = ""
            try:
                text = converter.convert(tmp_path).text_content or ""
            except Exception as e:
                st.error(f"Couldn't convert {f.name}: {e}")
            finally:
                os.unlink(tmp_path)

            out_name = os.path.splitext(f.name)[0] + ".md"
            results.append((out_name, text))

            with st.expander(f.name, expanded=(len(uploaded) == 1)):
                if text.strip():
                    st.download_button("⬇️ Download " + out_name, text, file_name=out_name,
                                       mime="text/markdown", key="dl_" + out_name)
                    st.caption("Or copy the text below — hover the box and click the copy icon in its top-right corner.")
                    st.code(text, language="markdown", height=300)
                else:
                    st.warning(
                        "This file came out empty — it's most likely a scan or a drawing "
                        "with no real text (common for plan sets). Use the other tab to split "
                        "or compress it, then upload the pieces straight to Claude."
                    )

        good = [(n, t) for n, t in results if t.strip()]
        if len(good) > 1:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                for name, text in good:
                    z.writestr(name, text)
            st.divider()
            st.download_button("⬇️ Download all as a ZIP", buf.getvalue(),
                               file_name="converted_markdown.zip", mime="application/zip")


# ===== TAB 2: Split or compress a plan set ==================================
with tab2:
    st.write(
        "Plan sets are usually too big for Claude (over 100 pages or 30MB). Compress or split "
        "one here, then upload straight into a Claude chat. **Compressing fixes the size (MB) "
        "limit; only splitting reduces the page count.**"
    )

    pf = st.file_uploader("Drop a plan PDF here", type=["pdf"], key="split_pdf")
    if pf:
        data = pf.getvalue()
        size_mb = len(data) / 1_000_000
        reader = PdfReader(io.BytesIO(data))
        n = len(reader.pages)
        base = os.path.splitext(pf.name)[0]
        st.info(f"**{pf.name}** — {n} pages, {size_mb:.1f} MB")
        show_limit_status(n, len(data))

        action = st.radio(
            "What do you want to do?",
            ["Compress the whole file (no splitting)",
             "Pull specific sheets (page range)",
             "Auto-split into chunks"],
        )

        # ---- Compress whole file ----
        if action == "Compress the whole file (no splitting)":
            if n > LIMIT_PAGES:
                st.warning(f"Heads up: this is {n} pages. Compression won't fix the {LIMIT_PAGES}-page "
                           "limit — you'll still need to pull a page range or split it.")
            if not has_gs():
                st.info("Compression isn't available yet — the Ghostscript add-on may still be installing after the last update. Give it a minute and refresh.")
            else:
                q = quality_picker("q_whole")
                if st.button("Compress"):
                    with st.spinner("Compressing…"):
                        out = compress_pdf(data, QUALITY[q])
                    out_mb = len(out) / 1_000_000
                    st.success(f"Compressed: {size_mb:.1f} MB → {out_mb:.1f} MB")
                    show_limit_status(n, len(out))
                    st.download_button(f"⬇️ Download compressed PDF ({out_mb:.1f} MB)", out,
                                       file_name=f"{base}_compressed.pdf", mime="application/pdf")

        # ---- Pull a page range ----
        elif action == "Pull specific sheets (page range)":
            rng = st.text_input("Pages to pull — use the PDF's page numbers, e.g. 12-40, 55")
            if rng:
                idx = parse_ranges(rng, n)
                if not idx:
                    st.error("Couldn't read those page numbers. Try something like 12-40.")
                else:
                    out = pdf_for_pages(reader, idx)
                    out_mb = len(out) / 1_000_000
                    show_limit_status(len(idx), len(out))
                    st.download_button(f"⬇️ Download {len(idx)} pages ({out_mb:.1f} MB)", out,
                                       file_name=f"{base}_pages.pdf", mime="application/pdf")
                    if has_gs():
                        with st.expander("Still too big? Compress these pages instead of splitting again"):
                            q = quality_picker("q_pages")
                            if st.button("Compress these pages", key="btn_pages"):
                                with st.spinner("Compressing…"):
                                    cout = compress_pdf(out, QUALITY[q])
                                cmb = len(cout) / 1_000_000
                                st.success(f"Compressed: {out_mb:.1f} MB → {cmb:.1f} MB")
                                show_limit_status(len(idx), len(cout))
                                st.download_button(f"⬇️ Download compressed ({cmb:.1f} MB)", cout,
                                                   file_name=f"{base}_pages_compressed.pdf",
                                                   mime="application/pdf", key="dl_pages_c")

        # ---- Auto-split ----
        else:
            per = st.number_input("Pages per chunk", min_value=1, max_value=99, value=95)
            if st.button("Split it"):
                part = 0
                for start in range(0, n, per):
                    part += 1
                    idx = list(range(start, min(start + per, n)))
                    b = pdf_for_pages(reader, idx)
                    mb = len(b) / 1_000_000
                    st.download_button(f"⬇️ Part {part}: pages {idx[0] + 1}–{idx[-1] + 1} ({mb:.1f} MB)",
                                       b, file_name=f"{base}_part{part}.pdf",
                                       mime="application/pdf", key=f"chunk_{part}")
                    show_limit_status(len(idx), len(b))
