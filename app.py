import os
import io
import time
import tempfile

import pandas as pd
import streamlit as st
import anthropic

import detector_core as core

MAX_FILES = 10

st.set_page_config(page_title="Detektor Teks AI", page_icon="🔎", layout="wide")


# ---------------- Kunci & pengaturan ----------------
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


def get_gdrive_folder_id():
    try:
        return st.secrets.get("GDRIVE_FOLDER_ID")
    except Exception:
        return None


DRIVE_CREDS = get_gdrive_credentials()
DRIVE_FOLDER = get_gdrive_folder_id()
DRIVE_ON = bool(DRIVE_CREDS and DRIVE_FOLDER)


# ---------------- Simpan ke Google Drive (opsional) ----------------
def upload_to_gdrive(data, name, creds_info, folder_id, mime="application/octet-stream"):
    # import di dalam fungsi: aplikasi tetap jalan walau paket Google belum dipasang
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload

    info = dict(creds_info)
    if "private_key" in info:
        info["private_key"] = info["private_key"].replace("\\n", "\n")
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive"])
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    meta = {"name": time.strftime("%Y%m%d_%H%M%S_") + os.path.basename(name), "parents": [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(bytes(data)), mimetype=mime, resumable=False)
    svc.files().create(body=meta, media_body=media, fields="id", supportsAllDrives=True).execute()


def drive_save(name, data, mime="application/octet-stream"):
    """Gagal menyimpan tidak pernah menghentikan analisis."""
    if not DRIVE_ON:
        return
    try:
        upload_to_gdrive(data, name, DRIVE_CREDS, DRIVE_FOLDER, mime)
    except Exception as e:
        msg = str(e)
        if "storageQuota" in msg or "storage quota" in msg.lower():
            st.warning("Gagal menyimpan ke Google Drive: service account tidak punya kuota di My Drive "
                       "biasa. Pakai Shared Drive (Google Workspace) atau metode OAuth.")
        else:
            st.warning(f"Gagal menyimpan ke Google Drive: {msg[:200]}")


# ---------------- Util ----------------
def read_upload(f):
    suffix = os.path.splitext(f.name)[1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(f.getbuffer())
        path = tmp.name
    try:
        return core.extract_text(path)
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
        st.dataframe(df, hide_index=True)
        st.caption("0 = mirip manusia, 100 = mirip AI. Perplexity hanya estimasi dari Claude.")
    with tab_b:
        dfc = pd.DataFrame([{
            "No": i, "Indikator": label,
            "Jawaban": "n/a" if ans is None else ("Ya" if ans else "Tidak"),
        } for i, (label, ans) in enumerate(r["checklist"], 1)])
        st.dataframe(dfc, hide_index=True)
    with tab_c:
        if not r["contoh"]:
            st.write("Tidak ada kalimat yang menonjol sebagai indikasi AI.")
        for i, c in enumerate(r["contoh"], 1):
            st.markdown(f"**{i}.** “{c.get('kutipan', '')}”")
            st.caption("Alasan: " + str(c.get("alasan", "")))
        st.markdown("**Saran:** " + str(r["saran"]))


def summary_csv(results):
    rows = []
    for name, r in results:
        row = {"file": name, "total_skor_ai": round(r["total"], 1), "kategori": r["category"],
               "checklist_ya": r["n_yes"], "jumlah_kata": r["n_words"]}
        for x in r["rows"]:
            row["skor_" + x["key"]] = x["skor"]
            row["nilai_" + x["key"]] = x["nilai"]
        rows.append(row)
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")


# ---------------- Tampilan ----------------
st.title("🔎 Detektor Teks AI")
st.caption("Statistik dihitung lokal; aspek subjektif dinilai Claude Haiku 5.5. "
           "Hasilnya probabilistik, bukan bukti pasti.")

with st.sidebar:
    st.header("Pengaturan")
    default_key = server_key()
    typed_key = st.text_input(
        "API key Claude", type="password",
        placeholder="Sudah terisi dari server" if default_key else "sk-ant-...",
        help="Dapatkan di platform.claude.com. Key tidak disimpan di aplikasi ini.",
    )
    api_key = typed_key or default_key
    st.caption(f"Model: `{core.MODEL}`")
    st.caption(f"Penilaian Claude memakai maks. {core.MAX_CHARS_LLM:,} karakter pertama; "
               "biaya sekitar Rp10-50 per dokumen.")

agree = True
if DRIVE_ON:
    st.info("Perhatian: dokumen yang Anda unggah atau tempel di sini akan disalin ke Google Drive "
            "pemilik aplikasi, bersama ringkasan skornya, untuk keperluan evaluasi.")
    agree = st.checkbox("Saya mengerti dan setuju dokumen saya disimpan di Google Drive pemilik aplikasi.")

tab_file, tab_text = st.tabs(["📎 Unggah file", "✍️ Tempel teks"])
with tab_file:
    files = st.file_uploader("PDF atau Word (.docx)", type=["pdf", "docx"], accept_multiple_files=True)
with tab_text:
    pasted = st.text_area("Tempel teks di sini (minimal ±300 kata)", height=250)

if st.button("Analisis", type="primary"):
    if not api_key:
        st.error("Masukkan API key Claude di sidebar terlebih dahulu.")
        st.stop()
    if not agree:
        st.error("Centang persetujuan penyimpanan dokumen terlebih dahulu.")
        st.stop()
    inputs = []
    for f in (files or [])[:MAX_FILES]:
        try:
            drive_save(f.name, f.getbuffer(), f.type or "application/octet-stream")
            inputs.append((f.name, read_upload(f)))
        except Exception as e:
            st.error(f"{f.name}: gagal dibaca ({e})")
    if files and len(files) > MAX_FILES:
        st.warning(f"Hanya {MAX_FILES} file pertama yang diproses.")
    if pasted.strip():
        drive_save("teks_ditempel.txt", pasted.strip().encode("utf-8"), "text/plain")
        inputs.append(("Teks yang ditempel", pasted.strip()))
    if not inputs:
        st.warning("Unggah file atau tempel teks dulu.")
        st.stop()

    client = anthropic.Anthropic(api_key=api_key)
    results = []
    for name, text in inputs:
        if len(core.tokenize(text)) < 50:
            st.warning(f"{name}: teks terlalu pendek atau PDF hasil scan (tanpa teks). Dilewati.")
            continue
        with st.spinner(f"Menganalisis {name} ..."):
            try:
                results.append((name, core.evaluate(client, text)))
            except Exception as e:
                st.error(f"{name}: gagal dianalisis. {e}")
    st.session_state["results"] = results
    if results:
        drive_save("hasil_deteksi.csv", summary_csv(results), "text/csv")

results = st.session_state.get("results", [])
if results:
    st.divider()
    for name, r in results:
        render_result(name, r)
        st.divider()
    st.download_button("⬇️ Unduh ringkasan skor (CSV)", summary_csv(results),
                       file_name="hasil_deteksi.csv", mime="text/csv")
    st.warning(core.DISCLAIMER)
