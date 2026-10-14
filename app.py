import os
import io
import time
import html
import tempfile

import pandas as pd
import streamlit as st
import anthropic

import detector_core as core

MAX_FILES = 10

# --- teks yang bisa Anda ubah ---
BADGE = "Claude Haiku 5.5"
SUBTITLE = ("Periksa apakah sebuah tulisan kemungkinan dibuat AI. "
            "Statistik dihitung lokal, aspek subjektif dinilai Claude.")

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root{--ink:#1d1d1f;--muted:#6e6e73;--line:#e8e8ed;--blue:#0071e3;}
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp p,.stApp li,.stApp label,.stApp button,
.stApp input,.stApp textarea,[data-testid="stCaptionContainer"],.hero,.score-card,.stat,.feat,
.section-title,.file-title,.fine{
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","SF Pro Text","Inter","Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
#MainMenu,footer,[data-testid="stDecoration"]{visibility:hidden;height:0;}
header[data-testid="stHeader"]{background:transparent;}
.block-container{max-width:980px;padding-top:2rem;padding-bottom:5rem;}

/* ---- hero ---- */
.hero{text-align:center;padding:2.2rem 0 1rem;}
.eyebrow{display:inline-block;background:#eaf3ff;color:var(--blue);font-weight:600;font-size:.82rem;
  padding:.38rem .95rem;border-radius:999px;letter-spacing:.01em;}
.hero-title{font-size:clamp(2.5rem,6.5vw,4.2rem);font-weight:700;letter-spacing:-.035em;line-height:1.04;
  margin:1.1rem 0 .9rem;color:var(--ink);}
.hero-title em{font-style:normal;background:linear-gradient(90deg,#0071e3 0%,#7a5cff 55%,#c04bd6 100%);
  -webkit-background-clip:text;background-clip:text;color:transparent;}
.hero-sub{color:var(--muted);font-size:1.18rem;max-width:660px;margin:0 auto;line-height:1.5;}
.feats{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin:2rem 0 2.2rem;}
.feat{background:#fff;border:1px solid var(--line);border-radius:20px;padding:1.2rem 1.3rem;
  box-shadow:0 4px 24px rgba(0,0,0,.04);}
.feat .ico{font-size:1.5rem;}
.feat b{display:block;margin:.4rem 0 .15rem;font-size:1rem;color:var(--ink);}
.feat span{color:var(--muted);font-size:.9rem;line-height:1.4;}
@media (max-width:720px){.feats,.stats{grid-template-columns:1fr;}}

/* ---- kartu & input ---- */
div[data-testid="stVerticalBlockBorderWrapper"],.st-key-main_card{background:#fff;border:1px solid var(--line)!important;
  border-radius:24px!important;box-shadow:0 8px 40px rgba(0,0,0,.05);padding:1rem 1.2rem!important;}
[data-testid="stFileUploaderDropzone"]{background:#fafafc;border:1.5px dashed #c7c7cc;border-radius:18px;padding:1.4rem;}
[data-testid="stFileUploaderDropzone"]:hover{border-color:var(--blue);background:#f4f9ff;}
textarea,input{border-radius:12px!important;}
[data-testid="stTabs"] button[role="tab"]{font-weight:600;font-size:.98rem;}
button[data-testid="stBaseButton-primary"],button[kind="primary"]{background:var(--blue);border:none;color:#fff;
  border-radius:999px;padding:.65rem 2rem;font-weight:600;font-size:1rem;box-shadow:0 4px 14px rgba(0,113,227,.3);
  transition:all .15s ease;}
button[data-testid="stBaseButton-primary"]:hover,button[kind="primary"]:hover{background:#0077ed;transform:translateY(-1px);
  box-shadow:0 8px 22px rgba(0,113,227,.35);}
[data-testid="stSidebar"]{background:#f5f5f7;border-right:1px solid var(--line);}
.section-title{font-size:1.5rem;font-weight:700;letter-spacing:-.02em;margin:.3rem 0 .6rem;color:var(--ink);}

/* ---- hasil ---- */
.file-title{font-size:1.3rem;font-weight:700;letter-spacing:-.02em;margin:1.4rem 0 .8rem;color:var(--ink);}
.score-card{background:#fff;border:1px solid var(--line);border-radius:28px;padding:2.2rem 2rem 1.8rem;
  box-shadow:0 10px 50px rgba(0,0,0,.06);text-align:center;}
.score-label{color:var(--muted);font-weight:600;font-size:.82rem;letter-spacing:.08em;text-transform:uppercase;}
.score-num{font-size:5.4rem;font-weight:700;letter-spacing:-.045em;line-height:1;margin:.5rem 0 .9rem;color:var(--ink);}
.score-num small{font-size:2rem;font-weight:600;color:var(--muted);margin-left:.2rem;letter-spacing:0;}
.pill{display:inline-block;padding:.45rem 1.1rem;border-radius:999px;font-weight:600;font-size:.95rem;}
.pill.green{background:#e6f7ec;color:#1a7f37;}.pill.blue{background:#e8f1ff;color:#0058b8;}
.pill.orange{background:#fff1dc;color:#a85a00;}.pill.red{background:#ffe9e7;color:#c2261b;}
.bar{height:10px;background:#efeff3;border-radius:999px;margin:1.5rem auto .3rem;max-width:520px;overflow:hidden;}
.bar>div{height:100%;border-radius:999px;}
.bar .green{background:#34c759;}.bar .blue{background:#0a84ff;}.bar .orange{background:#ff9f0a;}.bar .red{background:#ff453a;}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin:1rem 0 1.2rem;}
.stat{background:#fff;border:1px solid var(--line);border-radius:20px;padding:1.1rem 1.2rem;text-align:center;
  box-shadow:0 4px 24px rgba(0,0,0,.04);}
.stat b{display:block;font-size:1.7rem;letter-spacing:-.02em;color:var(--ink);}
.stat span{color:var(--muted);font-size:.85rem;}
.fine{color:var(--muted);font-size:.82rem;text-align:center;margin-top:2rem;line-height:1.5;}
"""

st.set_page_config(page_title="Detektor Teks AI", page_icon="🔎", layout="wide")


def html_block(*lines):
    """Gabungkan baris HTML tanpa spasi/baris kosong (supaya tidak dianggap blok kode oleh Markdown)."""
    return "".join(l.strip() for l in lines)


st.markdown("<style>" + CSS + "</style>", unsafe_allow_html=True)


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


def render_result(name, r):
    total = r["total"]
    tone = "green" if total <= 25 else "blue" if total <= 50 else "orange" if total <= 75 else "red"
    width = min(100, max(2, total))
    st.markdown(f'<div class="file-title">📄 {html.escape(name)}</div>', unsafe_allow_html=True)
    st.markdown(html_block(
        '<div class="score-card">',
        '<div class="score-label">Total skor AI</div>',
        f'<div class="score-num">{total:.1f}<small>%</small></div>',
        f'<span class="pill {tone}">{html.escape(r["category"])}</span>',
        f'<div class="bar"><div class="{tone}" style="width:{width:.1f}%"></div></div>',
        '</div>',
        '<div class="stats">',
        f'<div class="stat"><b>{r["n_yes"]}/{r["n_valid"]}</b><span>Checklist "Ya"</span></div>',
        f'<div class="stat"><b>{r["n_words"]:,}</b><span>Jumlah kata</span></div>',
        f'<div class="stat"><b style="font-size:1.05rem;line-height:1.7">{html.escape(r["checklist_category"])}</b><span>Kesimpulan checklist</span></div>',
        '</div>',
    ), unsafe_allow_html=True)
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
st.markdown(html_block(
    '<div class="hero">',
    f'<span class="eyebrow">{html.escape(BADGE)}</span>',
    '<div class="hero-title">Detektor <em>Teks AI</em></div>',
    f'<div class="hero-sub">{html.escape(SUBTITLE)}</div>',
    '</div>',
    '<div class="feats">',
    '<div class="feat"><div class="ico">📊</div><b>Statistik lokal</b><span>Variasi kalimat, kosakata, transisi, dan pola klise dihitung langsung.</span></div>',
    '<div class="feat"><div class="ico">🧠</div><b>Penilaian Claude</b><span>Aspek yang butuh pemahaman bahasa dinilai oleh model.</span></div>',
    '<div class="feat"><div class="ico">🔍</div><b>Transparan</b><span>Setiap parameter, skor, dan bobotnya bisa dilihat.</span></div>',
    '</div>',
), unsafe_allow_html=True)

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

st.markdown('<div class="section-title">Mulai analisis</div>', unsafe_allow_html=True)
try:
    card = st.container(border=True, key="main_card")
except TypeError:   # Streamlit versi lama
    card = st.container(border=True)
with card:
    tab_file, tab_text = st.tabs(["📎 Unggah file", "✍️ Tempel teks"])
    with tab_file:
        files = st.file_uploader("PDF atau Word (.docx)", type=["pdf", "docx"], accept_multiple_files=True,
                                 label_visibility="collapsed")
    with tab_text:
        pasted = st.text_area("Tempel teks di sini (minimal ±300 kata)", height=220,
                              placeholder="Tempel teks di sini (minimal ±300 kata)...",
                              label_visibility="collapsed")
    run = st.button("Analisis", type="primary")

if run:
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
    st.markdown(f'<div class="fine">{html.escape(core.DISCLAIMER)}</div>', unsafe_allow_html=True)
