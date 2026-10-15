import os
import io
import re
import time
import html
import tempfile
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import streamlit as st
import anthropic

import detector_core as core

MAX_FILES = 10

# --- Teks & Informasi Utama ---
BADGE = "this application was made specifically for Apeng's Friends"
SUBTITLE = ("Periksa apakah sebuah tulisan kemungkinan dibuat AI. "
            "Statistik dihitung langsung, aspek yang butuh pemahaman bahasa dinilai oleh model AI.")

CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap');
:root{--ember:#fc5000;--violet:#524ae9;--sulfur:#f5f28e;--limestone:#f7f6f2;--pumice:#e2e2df;--obsidian:#070607;--chalk:#ffffff;--muted:#6b6a66;}
.stApp{background:var(--limestone);color:var(--obsidian);}
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp p,.stApp li,.stApp label,.stApp button,
.stApp input,.stApp textarea,[data-testid="stCaptionContainer"],.hero,.score-card,.stat,.slider,
.section-title,.file-title,.fine{font-family:"DM Sans",ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;}

/* Sembunyikan Sidebar, Toolbar, Menu, Footer, dan Manage App */
[data-testid="stSidebar"],[data-testid="collapsedControl"],[data-testid="stSidebarCollapsedControl"],
#MainMenu,footer,[data-testid="stDecoration"],[data-testid="stAppToolbar"],.stAppToolbar,
[data-testid="stHeader"],div[class*="viewerBadge"],div[class*="manageAppButton"],
iframe[title="streamlit_app"] ~ div{display:none!important;visibility:hidden!important;height:0!important;
  width:0!important;opacity:0!important;pointer-events:none!important;}
.block-container{max-width:1200px;padding-top:2rem;padding-bottom:5rem;}

/* ---- hero ---- */
.hero{text-align:center;padding:2.4rem 0 .6rem;}
.eyebrow{display:inline-block;background:var(--sulfur);color:var(--obsidian);font-weight:500;font-size:.85rem;
  padding:.45rem 1.1rem;border-radius:800px;}
.hero-title{font-size:clamp(3rem,9vw,6.2rem);font-weight:500;letter-spacing:-.03em;line-height:.98;
  margin:1.3rem 0 1.1rem;color:var(--obsidian);}
.hero-title em{font-style:normal;color:var(--ember);}
.hero-sub{color:var(--muted);font-size:1.12rem;max-width:660px;margin:0 auto;line-height:1.55;}

/* ---- slide fitur ---- */
.slider{position:relative;overflow:hidden;border-radius:40px;background:var(--violet);color:var(--chalk);
  margin:2.2rem 0 2.4rem;}
.track{display:flex;width:400%;animation:slide 18s ease-in-out infinite;}
.slider:hover .track{animation-play-state:paused;}
.slide{flex:0 0 25%;box-sizing:border-box;padding:2.6rem 3rem 3.6rem;text-align:left;}
.slide .ico{font-size:2.2rem;}
.slide-tag{display:inline-block;margin-left:.8rem;background:var(--sulfur);color:var(--obsidian);font-size:.78rem;
  font-weight:500;padding:.3rem .85rem;border-radius:800px;vertical-align:middle;}
.slide-title{font-size:2.6rem;font-weight:500;letter-spacing:-.02em;line-height:1;margin:.9rem 0 .6rem;color:var(--chalk);}
.slide-desc{color:rgba(255,255,255,.82);font-size:1.05rem;line-height:1.55;max-width:620px;margin:0;}
.chips{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:1.3rem;}
.chips span{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.3);color:var(--chalk);font-size:.85rem;
  padding:.35rem .9rem;border-radius:800px;}
.dots{position:absolute;bottom:1.2rem;left:0;right:0;display:flex;justify-content:center;gap:.5rem;}
.dots i{display:block;width:8px;height:8px;border-radius:800px;background:rgba(255,255,255,.35);
  animation-duration:18s;animation-iteration-count:infinite;}
.dots i:nth-child(1){animation-name:d1;}.dots i:nth-child(2){animation-name:d2;}.dots i:nth-child(3){animation-name:d3;}
@keyframes slide{0%,22%{transform:translateX(0)}25%,47%{transform:translateX(-25%)}
  50%,72%{transform:translateX(-50%)}75%,100%{transform:translateX(-75%)}}
@keyframes d1{0%,22%{width:28px;background:#f5f28e}25%,72%{width:8px;background:rgba(255,255,255,.35)}75%,100%{width:28px;background:#f5f28e}}
@keyframes d2{0%,22%{width:8px;background:rgba(255,255,255,.35)}25%,47%{width:28px;background:#f5f28e}50%,100%{width:8px;background:rgba(255,255,255,.35)}}
@keyframes d3{0%,47%{width:8px;background:rgba(255,255,255,.35)}50%,72%{width:28px;background:#f5f28e}75%,100%{width:8px;background:rgba(255,255,255,.35)}}
@media (max-width:720px){.slide{padding:1.8rem 1.4rem 3.2rem;}.slide-title{font-size:1.9rem;}.stats{grid-template-columns:1fr!important;}}

/* ---- kartu & input ---- */
div[data-testid="stVerticalBlockBorderWrapper"],.st-key-main_card{background:var(--chalk);border:1px solid var(--pumice)!important;
  border-radius:40px!important;padding:1.2rem 1.5rem!important;}
[data-testid="stFileUploaderDropzone"]{background:var(--limestone);border:1.5px dashed #c8c8c3;border-radius:24px;padding:1.4rem;}
[data-testid="stFileUploaderDropzone"]:hover{border-color:var(--violet);background:#f1f0fd;}
textarea{border-radius:20px!important;}
[data-testid="stTextInput"] input{border-radius:100px!important;}
[data-testid="stTabs"] button[role="tab"]{font-weight:500;font-size:1rem;}
button[data-testid="stBaseButton-primary"],button[kind="primary"]{background:var(--ember);border:none;color:var(--chalk);
  border-radius:800px;padding:.7rem 2.4rem;font-weight:500;font-size:1rem;transition:all .15s ease;}
button[data-testid="stBaseButton-primary"]:hover,button[kind="primary"]:hover{background:#e04700;color:var(--chalk);
  transform:translateY(-1px);}
.section-title{font-size:2rem;font-weight:500;letter-spacing:-.02em;line-height:1;margin:.3rem 0 .8rem;color:var(--obsidian);}

/* ---- hasil ---- */
.file-title{font-size:1.4rem;font-weight:500;letter-spacing:-.01em;margin:1.4rem 0 .8rem;color:var(--obsidian);}
.score-card{background:var(--chalk);border:1px solid var(--pumice);border-radius:40px;padding:2.4rem 2rem 2rem;text-align:center;}
.score-label{color:var(--muted);font-weight:500;font-size:.82rem;letter-spacing:.08em;text-transform:uppercase;}
.score-num{font-size:5.6rem;font-weight:500;letter-spacing:-.045em;line-height:1;margin:.5rem 0 1rem;color:var(--obsidian);}
.score-num small{font-size:2rem;font-weight:500;color:var(--muted);margin-left:.2rem;letter-spacing:0;}
.pill{display:inline-block;padding:.45rem 1.2rem;border-radius:800px;font-weight:500;font-size:.95rem;}
.pill.green{background:#dff3e5;color:#176b32;}.pill.blue{background:#e6e4fc;color:#3a32c4;}
.pill.orange{background:var(--sulfur);color:#5c5400;}.pill.red{background:#ffe0d2;color:#b83a00;}
.bar{height:10px;background:var(--pumice);border-radius:800px;margin:1.5rem auto .3rem;max-width:520px;overflow:hidden;}
.bar>div{height:100%;border-radius:800px;}
.bar .green{background:#2fb457;}.bar .blue{background:var(--violet);}.bar .orange{background:#e8c800;}.bar .red{background:var(--ember);}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin:1rem 0 1.2rem;}
.stat{background:var(--chalk);border:1px solid var(--pumice);border-radius:24px;padding:1.2rem 1.2rem;text-align:center;}
.stat b{display:block;font-size:1.7rem;font-weight:500;letter-spacing:-.02em;color:var(--obsidian);}
.stat span{color:var(--muted);font-size:.85rem;}
.fine{color:var(--muted);font-size:.82rem;text-align:center;margin-top:2rem;line-height:1.5;}
"""

st.set_page_config(page_title="Apeng AI Content Detector", page_icon="🔎", layout="wide",
                   initial_sidebar_state="collapsed")


def html_block(*lines):
    """Gabungkan baris HTML tanpa spasi/baris kosong (supaya tidak dianggap blok kode oleh Markdown)."""
    return "".join(l.strip() for l in lines)


st.markdown("<style>" + CSS + "</style>", unsafe_allow_html=True)

# --- Percepat: kirim cuplikan (awal + tengah + akhir) ke AI, bukan seluruh teks ---
core.MAX_CHARS_LLM = 20000
if not getattr(core.ask_claude, "_fast", False):
    _orig_ask = core.ask_claude

    def _ask_fast(client, text):
        n = core.MAX_CHARS_LLM
        if len(text) > n:
            k = (n - 4) // 3
            mid = len(text) // 2
            text = text[:k] + "\n\n" + text[mid - k // 2: mid - k // 2 + k] + "\n\n" + text[-k:]
        return _orig_ask(client, text)

    _ask_fast._fast = True
    core.ask_claude = _ask_fast


@st.cache_resource
def get_pool():
    return ThreadPoolExecutor(max_workers=3)


# Label tabel tanpa nama merek
core.LABELS.update({
    "perplexity": "Perplexity (estimasi AI)",
    "typo": "Kesalahan ketik/ejaan (penilaian AI)",
    "personal": "Detail personal/konkret (penilaian AI)",
    "struktur": "Struktur dokumen terlalu rapi (penilaian AI)",
})


def scrub(text):
    """Pastikan teks dari mesin/error tidak menampilkan nama merek penyedia model atau tautan repositori."""
    text = re.sub(r"(?i)claude[\w.\-]*", "AI", str(text))
    text = re.sub(r"(?i)https?://github\.com/[^\s]+", "[protected repository]", text)
    text = re.sub(r"(?i)github", "repository", text)
    return re.sub(r"(?i)anthropic", "penyedia AI", text)


# ---------------- Kunci & pengaturan ----------------
def server_key():
    try:
        k = st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        k = None
    return k or os.environ.get("ANTHROPIC_API_KEY", "")


def get_secret(name):
    try:
        return st.secrets.get(name)
    except Exception:
        return None


DRIVE_URL = get_secret("DRIVE_WEBAPP_URL")
DRIVE_SECRET = get_secret("DRIVE_WEBAPP_SECRET")
DRIVE_ON = bool(DRIVE_URL and DRIVE_SECRET)


# ---------------- Simpan ke Google Drive (via Google Apps Script) ----------------
def upload_to_gdrive(data, name, mime="application/octet-stream"):
    import base64
    import requests

    payload = {
        "secret": DRIVE_SECRET,
        "name": time.strftime("%Y%m%d_%H%M%S_") + os.path.basename(name),
        "mime": mime,
        "data": base64.b64encode(bytes(data)).decode("ascii"),
    }
    resp = requests.post(DRIVE_URL, json=payload, timeout=120)
    resp.raise_for_status()
    try:
        res = resp.json()
    except Exception:
        raise RuntimeError("Respons Drive tidak valid. Pastikan deployment Apps Script diset 'Anyone'.")
    if not res.get("ok"):
        raise RuntimeError(res.get("error", "unknown"))


def drive_save(name, data, mime="application/octet-stream"):
    """Gagal menyimpan tidak pernah menghentikan analisis."""
    if not DRIVE_ON:
        return "Nonaktif (Secrets Belum Diatur)"
    try:
        upload_to_gdrive(data, name, mime)
        return "Tersimpan di Drive"
    except Exception as e:
        msg = str(e)
        st.warning(f"Gagal menyimpan ke Google Drive: {msg[:300]}")
        return f"Gagal: {msg[:50]}"


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
        n = re.sub(r"Penilaian Claude memakai [\d,]+ karakter pertama dari ([\d,]+)\.",
                   r"Penilaian AI memakai cuplikan awal, tengah, dan akhir dari \1 karakter.", n)
        st.caption("ℹ️ " + scrub(n))

    tab_a, tab_b, tab_c = st.tabs(["A. Skor parameter", "B. Checklist Ya/Tidak", "C. Contoh & saran"])
    with tab_a:
        df = pd.DataFrame([{
            "Parameter": scrub(x["parameter"]), "Nilai": x["nilai"],
            "Skor (0-100)": "n/a" if x["skor"] is None else str(x["skor"]),
            "Bobot (%)": str(x["bobot"]),
            "Kontribusi": "n/a" if x["kontribusi"] is None else str(x["kontribusi"]),
        } for x in r["rows"]])
        st.dataframe(df, hide_index=True)
        st.caption("0 = mirip manusia, 100 = mirip AI. Perplexity hanya estimasi dari model AI.")
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
            st.caption("Alasan: " + scrub(c.get("alasan", "")))
        st.markdown("**Saran:** " + scrub(r["saran"]))


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


SLIDES = [
    ("📊", "Statistik lokal", "Dihitung langsung",
     "Variasi kalimat, kosakata, transisi, dan pola klise diukur langsung dari teks Anda.",
     ["Burstiness", "Kosakata (MTLD)", "Transisi", "Frasa klise", "Trigram"]),
    ("🧠", "Penilaian AI", "Paham bahasa",
     "Aspek yang butuh pemahaman bahasa dinilai oleh model AI.",
     ["Perplexity", "Struktur dokumen", "Detail personal", "Ejaan"]),
    ("🔍", "Transparan", "Tanpa kotak hitam",
     "Setiap parameter, skor, dan bobotnya bisa dilihat.",
     ["Skor 0-100", "Bobot", "Kontribusi", "Checklist Ya/Tidak"]),
]


def slide_html(s):
    ico, title, tag, desc, chips = s
    return (f'<div class="slide"><div><span class="ico">{ico}</span><span class="slide-tag">{tag}</span></div>'
            f'<div class="slide-title">{title}</div><p class="slide-desc">{desc}</p>'
            '<div class="chips">' + "".join(f'<span>{c}</span>' for c in chips) + '</div></div>')


SLIDER_HTML = ('<div class="slider"><div class="track">'
               + "".join(slide_html(s) for s in SLIDES + SLIDES[:1])
               + '</div><div class="dots"><i></i><i></i><i></i></div></div>')


# ---------------- Tampilan Utama ----------------
st.markdown(html_block(
    '<div class="hero">',
    f'<span class="eyebrow">{html.escape(BADGE)}</span>',
    '<div class="hero-title">Apeng AI <em>Content Detector</em></div>',
    f'<div class="hero-sub">{html.escape(SUBTITLE)}</div>',
    '</div>',
    SLIDER_HTML,
), unsafe_allow_html=True)

default_key = server_key()
typed_key = ""

# Jika API key tidak ada di Secrets, tampilkan kolom input di halaman utama (bukan sidebar)
if not default_key:
    typed_key = st.text_input(
        "API key", type="password", placeholder="Masukkan API key layanan AI Anda",
        help="Key hanya dipakai selama sesi ini dan tidak disimpan.",
    )

api_key = typed_key or default_key

agree = True
if DRIVE_ON:
    st.info("Perhatian: dokumen yang Anda unggah atau tempel di sini akan disalin ke Google Drive pemilik aplikasi, bersama ringkasan skornya, untuk keperluan evaluasi.")
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
        st.error("Masukkan API key terlebih dahulu.")
        st.stop()
    if not agree:
        st.error("Centang persetujuan penyimpanan dokumen terlebih dahulu.")
        st.stop()

    uploads = []
    inputs = []
    for f in (files or [])[:MAX_FILES]:
        try:
            uploads.append((f.name, bytes(f.getbuffer()), f.type or "application/octet-stream"))
            inputs.append((f.name, read_upload(f)))
        except Exception as e:
            st.error(f"{f.name}: gagal dibaca ({scrub(e)})")

    if files and len(files) > MAX_FILES:
        st.warning(f"Hanya {MAX_FILES} file pertama yang diproses.")

    if pasted.strip():
        uploads.append(("teks_ditempel.txt", pasted.strip().encode("utf-8"), "text/plain"))
        inputs.append(("Teks yang ditempel", pasted.strip()))

    if not inputs:
        st.warning("Unggah file atau tempel teks dulu.")
        st.stop()

    # Simpan ke Drive di latar belakang, bersamaan dengan analisis
    pool = get_pool()
    drive_futs = []
    if DRIVE_ON:
        drive_futs = [(n, pool.submit(upload_to_gdrive, d, n, m)) for n, d, m in uploads]

    client = anthropic.Anthropic(api_key=api_key)
    todo = []
    for name, text in inputs:
        if len(core.tokenize(text)) < 50:
            st.warning(f"{name}: teks terlalu pendek atau PDF hasil scan (tanpa teks). Dilewati.")
            continue
        todo.append((name, text))

    results = []
    if todo:
        with st.spinner(f"Menganalisis {len(todo)} dokumen ..."):
            with ThreadPoolExecutor(max_workers=3) as ex:
                futs = [(n, ex.submit(core.evaluate, client, t)) for n, t in todo]
                for n, fu in futs:
                    try:
                        results.append((n, fu.result()))
                    except Exception as e:
                        st.error(f"{n}: gagal dianalisis. {scrub(e)}")

    st.session_state["results"] = results

    if DRIVE_ON:
        for n, fu in drive_futs:
            if fu.done() and fu.exception():
                st.warning(f"Gagal menyimpan {n} ke Google Drive: {str(fu.exception())[:200]}")
        if results:
            pool.submit(upload_to_gdrive, summary_csv(results), "hasil_deteksi.csv", "text/csv")

results = st.session_state.get("results", [])
if results:
    st.divider()
    for name, r in results:
        render_result(name, r)
        st.divider()
    st.download_button("⬇️ Unduh ringkasan skor (CSV)", summary_csv(results),
                       file_name="hasil_deteksi.csv", mime="text/csv")

st.markdown(html_block(
    '<div class="fine">',
    (html.escape(core.DISCLAIMER) + "<br>") if results else "",
    'Dokumen yang diunggah hanya digunakan untuk analisis dan evaluasi aplikasi ini.',
    '</div>',
), unsafe_allow_html=True)
