"""
Good Air File Converter
A simple drag-and-drop interface for MarkItDown, hosted on Streamlit Community Cloud.
Team members open the link, enter the team password, drop in a file, and download
lightweight Markdown text to attach to Claude — no terminal, no install.
"""

import io
import os
import tempfile
import zipfile

import streamlit as st
from markitdown import MarkItDown

st.set_page_config(page_title="Good Air File Converter", page_icon="🌬️", layout="centered")


# ---- Simple shared-password gate -------------------------------------------
def check_password() -> bool:
    """Returns True once the correct team password has been entered."""
    def password_entered():
        if st.session_state.get("password") == st.secrets.get("app_password"):
            st.session_state["authenticated"] = True
            del st.session_state["password"]
        else:
            st.session_state["authenticated"] = False

    if st.session_state.get("authenticated"):
        return True

    st.title("🌬️ Good Air File Converter")
    st.text_input("Team password", type="password", on_change=password_entered, key="password")
    if "authenticated" in st.session_state and not st.session_state["authenticated"]:
        st.error("Incorrect password — try again.")
    return False


if not check_password():
    st.stop()
# ---------------------------------------------------------------------------


converter = MarkItDown()

st.title("🌬️ Good Air File Converter")
st.write(
    "Drop in PDFs, Word, Excel, or PowerPoint files. "
    "You'll get back lightweight text (Markdown) to attach to Claude instead of the heavy original."
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
                st.text_area("Preview", text, height=300, key="ta_" + out_name)
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
