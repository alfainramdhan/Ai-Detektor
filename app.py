import os
import tempfile

import pandas as pd
import streamlit as st
import anthropic

import detector_core as core

MAX_FILES = 10

st.set_page_config(page_title="Detektor Teks AI", page_icon="🔎", layout="wide")


def server_key():
    try:
        k = st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        k = None
    return k or os.environ.get("ANTHROPIC_API_KEY", "")


def get_gdrive_credentials():
    try:
        return dict(st.secrets["gdrive_service_account"])
    except Exception:
        return None


def read_upload_and_sync_drive(f, gdrive_creds, folder_id):
    suffix = os.path.splitext(f.name)[1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(f.getbuffer())
        path = tmp.name
    try:
        text_content = core.extract_text(path)
        if gdrive_creds and folder_id:
            core.upload_to_gdrive(path, f.name, gdrive_creds, folder_id)
        return text_content
    finally:
        if os.path.exists(path):
            os.remove(path)


def render_category(total, text):
    if total <= 25:
        st.success(text)
    elif total <= 50:
        st.info(text)
    elif total <= 75:
        st.warning(text)
    else:
        st.error(text)


def render_result(name, r):
    st.subheader(f"📄 {name}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total skor AI", f"{r['total']:.1f}%")
    c2.metric("Checklist 'Ya'", f"{r['n_yes']}/{r['n_valid']}")
    c3.metric("Jumlah kata", f"{r['n_words']:,}")
    st.progress(min(100, max(0, int(round(r["total"])))) / 100)
    render_category(r["total"], f"**{r['category']}**  ·  Checklist: {r['checklist_category']}")
    for n in r["notes"]:
        st.caption("ℹ️ " + n)

    tab_a, tab_b, tab_c = st.tabs(["A. Skor parameter", "B. Checklist Ya/Tidak", "C. Contoh & saran"])
    with tab_a:
        df = pd.DataFrame([{
            "Parameter": x["parameter"], "Nilai": x["nilai"],
            "Skor (0-100)": "n/a" if x["skor"] is None else str(x["skor"]),
            "Bobot (%)": str(x["bobot"]),
            "Kontribusi": "n/a" if x["kontribusi"] is None else str(x["kontribusi"]),
        } for x in r["rows"]])