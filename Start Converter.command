#!/bin/bash
# Double-click this file to start the Good Air File Converter.
# It opens the app in your web browser. Leave this window open while the team uses it.
cd "$(dirname "$0")"
source .venv/bin/activate
streamlit run convert_app.py
