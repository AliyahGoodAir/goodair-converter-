"""
File Markdown Tool — Good Air Inc.
A drag-and-drop interface for MarkItDown, hosted on Streamlit Community Cloud.
Team members open the link, sign in once (with optional "stay signed in"),
then copy or download lightweight Markdown to attach to Claude.
"""

import io
import os
import time
import tempfile
import zipfile
import hashlib
from datetime import datetime, timedelta

import streamlit as st
import extra_streamlit_components as stx
from markitdown import MarkItDown

LOGO = "goodair_logo.png"  # upload this file to the repo with EXACTLY this name

st.set_page_config(page_title="File Markdown Tool", page_icon="❄️", layout="centered")

cookie_manager = stx.CookieManager()


def show_logo():
    if os.path.exists(LOGO):
        st.image(LOGO, width=280)


def token_for(pw: str) -> str:
    """A non-reversible stamp of the password, safe to store in a browser cookie."""
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


# ---- Sign-in with optional "stay signed in" --------------------------------
def check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True

    secret = st.secrets.get("app_password", "")

    # Returning user with a valid "remember me" cookie
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
                cookie_manager.set(
                    "fmt_auth",
                    token_for(pw),
                    expires_at=datetime.now() + timedelta(days=30),
                )
                time.sleep(0.5)  # give the cookie a moment to save
            st.rerun()
        else:
            st.error("Incorrect password — try again.")
    return False


if not check_password():
    st.stop()
# ---------------------------------------------------------------------------


# Sign-out lives in the side panel (the > arrow, top-left)
with st.sidebar:
    if st.button("Sign out"):
        try:
            cookie_manager.delete("fmt_auth")
        except Exception:
            pass
        st.session_state.clear()
        time.sleep(0.3)
        st.rerun()


converter = MarkItDown()

show_logo()
st.title("File Markdown Tool")
st.write(
    "Drop in PDFs, Word, Excel, or PowerPoint files. You'll get back lightweight text "
    "(Markdown) you can copy or download to attach to Claude instead of the heavy original."
)

uploaded = st.file_uploader(
    "Drag files here, or click to browse",
    type=["pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls", "csv", "html", "htm", "txt"],
    accept_multiple_files=True,
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
                st.download_button(
                    "⬇️ Download " + out_name,
                    text,
                    file_name=out_name,
                    mime="text/markdown",
                    key="dl_" + out_name,
                )
                st.caption("Or copy the text below — hover the box and click the copy icon in its top-right corner.")
                st.code(text, language="markdown", height=300)
            else:
                st.warning(
                    "This file came out empty — it's most likely a scan or a drawing "
                    "with no real text in it (common for mechanical plan sets). "
                    "Those need OCR, which is a separate step."
                )

    good = [(n, t) for n, t in results if t.strip()]
    if len(good) > 1:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for name, text in good:
                z.writestr(name, text)
        st.divider()
        st.download_button(
            "⬇️ Download all as a ZIP",
            buf.getvalue(),
            file_name="converted_markdown.zip",
            mime="application/zip",
        )
