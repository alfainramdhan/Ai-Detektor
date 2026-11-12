import os
import io
import re
import time
import html
import tempfile
from concurrent.futures import ThreadPoolExecutor, wait

import pandas as pd
import streamlit as st
import anthropic

import detector_core as core

MAX_FILES = 10

# --- Teks & Informasi Utama ---
BADGE = "this application was made specifically for Apeng's Friends"
SUBTITLE = (
    "Periksa apakah sebuah tulisan kemungkinan dibuat AI. "
    "Statistik dihitung langsung, aspek yang butuh pemahaman bahasa dinilai oleh model AI."
)

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;500&family=Cormorant+Garamond:ital,wght@0,400;1,400&family=IBM+Plex+Mono:wght@400&display=swap');
:root{--black:#000000;--cream:#fbfaf6;--charcoal:#222222;--mist:#e3e3e9;--ash:#dadbdd;--white:#ffffff;--rust:#813413;--muted:#5c5a56;}
.stApp{background:var(--cream);color:var(--black);}
[data-testid="stAppViewContainer"]{overflow-x:hidden;}
.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp p,.stApp li,.stApp label,.stApp input,.stApp textarea,
[data-testid="stCaptionContainer"],.hero-sub,.slide-desc,.score-card,.stat,.fine{font-family:"Archivo",ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;}
.stApp button,.eyebrow,.mono,.chips,.pill,.score-label,.stat span,[data-testid="stTabs"] button[role="tab"]{font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;}
.hero-title,.hero-title em,.section-title,.file-title,.slide-title,.slide-num,.score-num,.stat b,.marquee span{font-family:"Cormorant Garamond","Times New Roman",serif;font-weight:400;}
.score-num,.stat b,.slide-num{font-variant-numeric:lining-nums;}

/* Sembunyikan Sidebar, Toolbar, Menu, Footer, dan Manage App */
[data-testid="stSidebar"],[data-testid="collapsedControl"],[data-testid="stSidebarCollapsedControl"],
#MainMenu,footer,[data-testid="stDecoration"],[data-testid="stAppToolbar"],.stAppToolbar,
[data-testid="stHeader"],div[class*="viewerBadge"],div[class*="manageAppButton"],
iframe[title="streamlit_app"] ~ div{display:none!important;visibility:hidden!important;height:0!important;
  width:0!important;opacity:0!important;pointer-events:none!important;}
.block-container{max-width:1200px;padding-top:1.5rem;padding-bottom:5rem;}

/* ---- hero (panel hitam membulat) ---- */
.hero{background:var(--black);color:var(--cream);border-radius:24px;text-align:center;padding:3.4rem 1.5rem 0;overflow:hidden;}
.eyebrow{display:inline-block;color:var(--cream);border:1px solid var(--cream);font-size:.75rem;letter-spacing:.36px;
  text-transform:uppercase;padding:.55rem 1.3rem;border-radius:9999px;}
.hero-title{font-size:clamp(3.2rem,10vw,7.4rem);line-height:1;margin:1.4rem 0 1rem;color:var(--cream);}
.hero-title em{font-style:italic;}
.hero-sub{color:rgba(251,250,246,.86);font-size:1.12rem;line-height:1.5;max-width:620px;margin:0 auto;}
.marquee{margin-top:2.6rem;padding:1.1rem 0;border-top:1px solid rgba(251,250,246,.25);overflow:hidden;white-space:nowrap;}
.marquee-in{display:inline-flex;animation:marq 20s linear infinite;}
.marquee span{font-size:clamp(1.8rem,4.5vw,3.2rem);line-height:1.3;color:var(--cream);padding:0 1.4rem;}
.marquee i{font-style:normal;color:rgba(251,250,246,.45);font-size:clamp(1.8rem,4.5vw,3.2rem);}
@keyframes marq{to{transform:translateX(-50%)}}

/* ---- slide fitur (diptych membulat) ---- */
.slider{overflow:hidden;margin:1.2rem -10px 2.4rem 0;}
.track{display:flex;width:400%;animation:slide 18s ease-in-out infinite;}
.slider:hover .track{animation-play-state:paused;}
.slide{flex:0 0 25%;box-sizing:border-box;padding-right:10px;display:grid;grid-template-columns:1.3fr .7fr;gap:10px;}
.pn{border-radius:24px;padding:1.9rem 2.1rem;min-height:340px;display:flex;flex-direction:column;justify-content:space-between;gap:1.6rem;box-sizing:border-box;}
.pn-rust{background:var(--rust);color:var(--cream);}
.pn-black{background:var(--black);color:var(--cream);}
.pn-mist{background:var(--mist);color:var(--black);}
.mono{font-size:.75rem;letter-spacing:.36px;text-transform:uppercase;}
.slide-title{font-size:clamp(2.6rem,5.5vw,4.4rem);line-height:1;margin:0 0 .9rem;}
.slide-desc{font-size:1.05rem;line-height:1.55;max-width:520px;margin:0;opacity:.94;}
.chips{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:1.3rem;}
.chips span{border:1px solid currentColor;font-size:.72rem;letter-spacing:.36px;text-transform:uppercase;padding:.42rem .95rem;border-radius:9999px;}
.slide-num{font-size:clamp(6rem,15vw,10.5rem);line-height:.8;text-align:right;}
.dots{display:flex;justify-content:center;gap:.5rem;padding:1.1rem 10px 0 0;}
.dots i{display:block;width:8px;height:8px;border-radius:9999px;background:var(--ash);animation-duration:18s;animation-iteration-count:infinite;}
.dots i:nth-child(1){animation-name:d1;}.dots i:nth-child(2){animation-name:d2;}.dots i:nth-child(3){animation-name:d3;}
@keyframes slide{0%,22%{transform:translateX(0)}25%,47%{transform:translateX(-25%)}
  50%,72%{transform:translateX(-50%)}75%,100%{transform:translateX(-75%)}}
@keyframes d1{0%,22%{width:28px;background:#000}25%,72%{width:8px;background:#dadbdd}75%,100%{width:28px;background:#000}}
@keyframes d2{0%,22%{width:8px;background:#dadbdd}25%,47%{width:28px;background:#000}50%,100%{width:8px;background:#dadbdd}}
@keyframes d3{0%,47%{width:8px;background:#dadbdd}50%,72%{width:28px;background:#000}75%,100%{width:8px;background:#dadbdd}}
@media (max-width:720px){.slide{grid-template-columns:1fr;}.pn-num{display:none;}.pn{padding:1.5rem 1.4rem;min-height:300px;}
  .hero{padding-top:2.4rem;}.stats{grid-template-columns:1fr!important;}}

/* ---- kartu & input ---- */
div[data-testid="stVerticalBlockBorderWrapper"],.st-key-main_card{background:var(--white);border:1px solid var(--ash)!important;
  border-radius:24px!important;box-shadow:none;padding:1.2rem 1.5rem!important;}
[data-testid="stFileUploaderDropzone"]{background:var(--cream);border:1.5px dashed #b9bac0;border-radius:16px;padding:1.4rem;}
[data-testid="stFileUploaderDropzone"]:hover{border-color:var(--rust);background:#f6f1ec;}
textarea,[data-testid="stTextInput"] input{border-radius:12px!important;}
[data-testid="stTabs"] button[role="tab"]{font-size:.8rem;letter-spacing:.42px;text-transform:uppercase;}
button[data-testid="stBaseButton-primary"],button[kind="primary"]{background:var(--black);border:none;color:var(--cream);
  border-radius:9999px;padding:1rem 2.6rem;font-size:.85rem;letter-spacing:.42px;text-transform:uppercase;box-shadow:none;transition:background .15s ease;}
button[data-testid="stBaseButton-primary"]:hover,button[kind="primary"]:hover{background:var(--rust);color:var(--cream);}
.section-title{font-size:clamp(2.2rem,5vw,3rem);line-height:1;margin:.4rem 0 .9rem;color:var(--black);}

/* ---- hasil ---- */
.file-title{font-size:2rem;line-height:1.05;margin:1.6rem 0 .9rem;color:var(--black);}
.score-card{background:var(--white);border:1px solid var(--ash);border-radius:24px;padding:2.4rem 2rem 2rem;text-align:center;}
.score-label{color:var(--muted);font-size:.75rem;letter-spacing:.36px;text-transform:uppercase;}
.score-num{font-size:7rem;line-height:.9;margin:.7rem 0 1.1rem;color:var(--black);}
.score-num small{font-size:2.6rem;color:var(--muted);margin-left:.2rem;}
.pill{display:inline-block;padding:.5rem 1.2rem;border-radius:9999px;font-size:.78rem;letter-spacing:.36px;text-transform:uppercase;}
.pill.green{background:#e4ebe0;color:#1f3a1b;}.pill.blue{background:var(--mist);color:var(--charcoal);}
.pill.orange{background:#f0e2d6;color:#6a2a0e;}.pill.red{background:var(--rust);color:var(--cream);}
.bar{height:10px;background:var(--mist);border-radius:9999px;margin:1.5rem auto .3rem;max-width:520px;overflow:hidden;}
.bar>div{height:100%;border-radius:9999px;}
.bar .green{background:#5f7f58;}.bar .blue{background:#8b8d99;}.bar .orange{background:#b8652f;}.bar .red{background:var(--rust);}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:1rem 0 1.2rem;}
.stat{background:var(--white);border:1px solid var(--ash);border-radius:16px;padding:1.2rem;text-align:center;}
.stat b{display:block;font-size:2.4rem;line-height:1.1;color:var(--black);}
.stat span{color:var(--muted);font-size:.72rem;letter-spacing:.36px;text-transform:uppercase;}
.fine{color:var(--muted);font-size:.8rem;text-align:center;margin-top:2rem;line-height:1.6;}

/* ===== NAV, SECTION, CARA KERJA, PERBANDINGAN, FAQ ===== */
[data-testid="stMain"]{scroll-behavior:smooth;}
[id]{scroll-margin-top:96px;}
.block-container{padding-top:5.4rem;}
.nav{position:fixed;top:14px;left:50%;transform:translateX(-50%);width:min(1160px,calc(100% - 28px));z-index:999;display:flex;
  align-items:center;justify-content:space-between;background:rgba(251,250,246,.92);backdrop-filter:blur(10px);
  border:1px solid var(--ash);border-radius:9999px;padding:.5rem .5rem .5rem 1.5rem;box-sizing:border-box;}
.nav-brand{font-family:"Cormorant Garamond",serif;font-size:1.7rem;line-height:1;color:var(--black)!important;text-decoration:none!important;}
.nav-brand i{font-style:italic;}
.nav-links{display:flex;gap:2rem;}
.nav-links a{font-family:"IBM Plex Mono",monospace;font-size:.76rem;letter-spacing:.42px;text-transform:uppercase;color:var(--black)!important;
  text-decoration:none!important;padding:.4rem 0;border-bottom:1px solid transparent;transition:border-color .15s;}
.nav-links a:hover{border-bottom-color:var(--rust);}
.nav-cta{font-family:"IBM Plex Mono",monospace;font-size:.76rem;letter-spacing:.42px;text-transform:uppercase;background:var(--black);
  color:var(--cream)!important;text-decoration:none!important;padding:.75rem 1.6rem;border-radius:9999px;transition:background .15s;}
.nav-cta:hover{background:var(--rust);}
.sec{margin:5.5rem 0 1.5rem;}
.sec-eyebrow{display:flex;align-items:center;gap:.8rem;font-family:"IBM Plex Mono",monospace;font-size:.76rem;letter-spacing:.42px;
  text-transform:uppercase;color:var(--rust);}
.sec-eyebrow i{display:block;width:34px;height:1px;background:var(--rust);}
.sec-title{font-family:"Cormorant Garamond",serif;font-size:clamp(2.5rem,6vw,4.4rem);line-height:1;margin:1rem 0 1rem;color:var(--black);max-width:860px;}
.sec-title em{font-style:italic;}
.sec-sub{color:var(--muted);font-size:1.08rem;line-height:1.65;max-width:640px;margin:0 0 2.4rem;}
.steps{position:relative;display:grid;grid-template-columns:repeat(6,1fr);gap:14px;}
.steps:before{content:"";position:absolute;top:30px;left:8%;right:8%;border-top:2px dashed #cdc7bb;}
.step{position:relative;text-align:center;padding:0 .4rem;}
.step-dot{position:relative;width:60px;height:60px;margin:0 auto 1.1rem;border-radius:9999px;background:var(--cream);border:1.5px solid #cdc7bb;
  display:flex;align-items:center;justify-content:center;font-family:"Cormorant Garamond",serif;font-size:1.7rem;color:var(--black);
  transition:all .2s ease;}
.step:hover .step-dot{background:var(--black);color:var(--cream);border-color:var(--black);transform:translateY(-4px);}
.step.ai .step-dot{background:var(--rust);color:var(--cream);border-color:var(--rust);}
.step.local .step-dot{background:var(--mist);border-color:var(--mist);}
.step-t{font-family:"Archivo",sans-serif;font-weight:500;font-size:1.02rem;margin-bottom:.35rem;}
.step p{color:var(--muted);font-size:.9rem;line-height:1.5;margin:0 0 .7rem;}
.step-tag{display:inline-block;font-family:"IBM Plex Mono",monospace;font-size:.66rem;letter-spacing:.36px;text-transform:uppercase;
  border:1px solid var(--ash);border-radius:9999px;padding:.25rem .7rem;color:var(--charcoal);}
.step.ai .step-tag{border-color:var(--rust);color:var(--rust);}
.cmp-wrap{overflow-x:auto;border:1px solid var(--ash);border-radius:24px;background:var(--white);}
.cmp{width:100%;min-width:760px;border-collapse:collapse;font-family:"Archivo",sans-serif;}
.cmp th{font-family:"IBM Plex Mono",monospace;font-weight:400;font-size:.72rem;letter-spacing:.36px;text-transform:uppercase;
  color:var(--muted);text-align:left;padding:1.2rem 1.4rem;background:#f3f1ea;}
.cmp th.us{background:var(--rust);color:var(--cream);}
.cmp td{padding:1.1rem 1.4rem;border-top:1px solid #eee9df;font-size:.97rem;vertical-align:top;color:var(--charcoal);}
.cmp td:first-child{font-weight:500;color:var(--black);}
.cmp td.us{background:#f7ece6;color:var(--black);}
.cmp .y b{color:#1f5a2b;}.cmp .n b{color:#a33a10;}.cmp .p b{color:#77746e;}
.cmp-note{color:var(--muted);font-size:.82rem;margin:1rem .2rem 0;line-height:1.6;}
.faq{max-width:900px;}
.faq details{border-top:1px solid var(--ash);padding:1.25rem 0;}
.faq details:last-child{border-bottom:1px solid var(--ash);}
.faq summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:1rem;
  font-family:"Cormorant Garamond",serif;font-size:clamp(1.4rem,3vw,1.8rem);line-height:1.15;color:var(--black);}
.faq summary::-webkit-details-marker{display:none;}
.faq summary:after{content:"+";flex:none;width:2.3rem;height:2.3rem;border:1px solid var(--ash);border-radius:9999px;display:flex;
  align-items:center;justify-content:center;font-family:"IBM Plex Mono",monospace;font-size:1.2rem;transition:all .15s;}
.faq details[open] summary:after{content:"–";background:var(--black);color:var(--cream);border-color:var(--black);}
.faq p{margin:.9rem 0 0;max-width:720px;color:var(--muted);line-height:1.7;font-size:1rem;}
@media (max-width:900px){.steps{grid-template-columns:repeat(2,1fr);row-gap:2rem;}.steps:before{display:none;}}

/* ===== HUMANIZER ===== */
.hz-note{background:#f7ece6;border:1px solid #ecd6c9;border-radius:16px;padding:1rem 1.2rem;color:var(--charcoal);
  font-family:"Archivo",sans-serif;font-size:.92rem;line-height:1.6;margin:.4rem 0 1rem;}
.hz-text{background:var(--white);border:1px solid var(--ash);border-radius:16px;padding:1.4rem 1.6rem;white-space:pre-wrap;
  font-family:"Archivo",sans-serif;font-size:1rem;line-height:1.75;color:var(--black);max-height:620px;overflow-y:auto;}
.hz-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:1rem 0 1.2rem;}
@media (max-width:720px){.hz-grid{grid-template-columns:1fr;}}
.hz-feat{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;}
.hz-feat div{background:var(--white);border:1px solid var(--ash);border-radius:20px;padding:1.4rem;}
.hz-feat b{display:block;font-family:"Cormorant Garamond",serif;font-weight:400;font-size:1.6rem;line-height:1.1;margin-bottom:.5rem;}
.hz-feat p{margin:0;color:var(--muted);font-size:.92rem;line-height:1.55;}
@media (max-width:900px){.hz-feat{grid-template-columns:repeat(2,1fr);}}
@media (max-width:560px){.hz-feat{grid-template-columns:1fr;}}
@media (max-width:720px){.nav-links{display:none;}.nav{padding-left:1.1rem;}.sec{margin-top:4rem;}}
"""

st.set_page_config(
    page_title="Apeng AI Content Detector", page_icon="🔎", layout="wide", initial_sidebar_state="collapsed"
)


def html_block(*lines):
    """Gabungkan baris HTML tanpa spasi/baris kosong (supaya tidak dianggap blok kode oleh Markdown)."""
    return "".join(l.strip() for l in lines)


st.markdown("<style>" + CSS + "</style>", unsafe_allow_html=True)

# --- Kirim cuplikan ke AI ---
core.MAX_CHARS_LLM = 12000
if not getattr(core.ask_claude, "_fast", False):
    _orig_ask = core.ask_claude

    def _ask_fast(client, text):
        n = core.MAX_CHARS_LLM
        if len(text) > n:
            k = (n - 4) // 3
            mid = len(text) // 2
            text = text[:k] + "\n\n" + text[mid - k // 2 : mid - k // 2 + k] + "\n\n" + text[-k:]
        return _orig_ask(client, text)

    _ask_fast._fast = True
    core.ask_claude = _ask_fast


@st.cache_resource
def get_pool():
    return ThreadPoolExecutor(max_workers=3)


def scrub(text):
    """Pastikan teks dari mesin/error tidak menampilkan nama merek penyedia model atau tautan repositori."""
    text = re.sub(r"(?i)claude[\w.\-]*", "AI", str(text))
    text = re.sub(r"(?i)https?://github\.com/[^\s]+", "[protected repository]", text)
    text = re.sub(r"(?i)github", "repository", text)
    return re.sub(r"(?i)anthropic", "penyedia AI", text)


# ---------------- Kunci & Pengaturan ----------------
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


def _bg_upload(name, data, mime):
    """Upload dengan 2x percobaan."""
    last = None
    for attempt in range(2):
        try:
            upload_to_gdrive(data, name, mime)
            print(f"[drive] OK {name} ({len(data) / 1024:.0f} KB)", flush=True)
            return
        except Exception as e:
            last = e
            print(f"[drive] GAGAL {name} ({len(data) / 1024:.0f} KB) percobaan {attempt + 1}: {e}", flush=True)
            time.sleep(2)
    raise last


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
    tone = "green" if total <= 25.0 else "blue" if total <= 50.0 else "orange" if total <= 75.0 else "red"
    width = min(100, max(2, total))
    st.markdown(f'<div class="file-title">📄 {html.escape(name)}</div>', unsafe_allow_html=True)
    st.markdown(
        html_block(
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
        ),
        unsafe_allow_html=True,
    )
    for n in r["notes"]:
        n = re.sub(
            r"Penilaian Claude memakai [\d,]+ karakter pertama dari ([\d,]+)\.",
            r"Penilaian AI memakai cuplikan awal, tengah, dan akhir dari \1 karakter.",
            n,
        )
        st.caption("ℹ️ " + scrub(n))

    tab_a, tab_b, tab_c = st.tabs(["A. Skor parameter (16)", "B. Checklist Ya/Tidak (22)", "C. Contoh & saran"])
    with tab_a:
        df = pd.DataFrame(
            [
                {
                    "Parameter": scrub(x["parameter"]),
                    "Nilai": x["nilai"],
                    "Skor (0-100)": "n/a" if x["skor"] is None else str(x["skor"]),
                    "Bobot (%)": str(x["bobot"]),
                    "Kontribusi": "n/a" if x["kontribusi"] is None else str(x["kontribusi"]),
                }
                for x in r["rows"]
            ]
        )
        st.dataframe(df, hide_index=True)
        st.caption("0 = mirip manusia, 100 = mirip AI. Parameter LLM dievaluasi via model AI terintegrasi.")
    with tab_b:
        dfc = pd.DataFrame(
            [
                {
                    "No": i,
                    "Indikator Checklist": label,
                    "Jawaban": "n/a" if ans is None else ("Ya" if ans else "Tidak"),
                }
                for i, (label, ans) in enumerate(r["checklist"], 1)
            ]
        )
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
        row = {
            "file": name,
            "total_skor_ai": round(r["total"], 1),
            "kategori": r["category"],
            "checklist_ya": r["n_yes"],
            "jumlah_kata": r["n_words"],
        }
        for x in r["rows"]:
            row["skor_" + x["key"]] = x["skor"]
            row["nilai_" + x["key"]] = x["nilai"]
        rows.append(row)
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")


def _safe_stem(name):
    stem = os.path.splitext(os.path.basename(name))[0] or "teks"
    return re.sub(r"[^\w\-]+", "_", stem)[:60]


def render_humanize_result(name, r, idx):
    st.markdown(f'<div class="file-title">✍️ {html.escape(name)}</div>', unsafe_allow_html=True)
    if r["status"] != "ok":
        st.warning("Tidak disunting: " + scrub(r["reason"]))
        return

    mb, ma = r["metrics_before"], r["metrics_after"]
    st.markdown(
        html_block(
            '<div class="hz-grid">',
            f'<div class="stat"><b>{mb["n_pass"]}/{mb["n_rows"]} → {ma["n_pass"]}/{ma["n_rows"]}</b><span>Metrik lulus</span></div>',
            f'<div class="stat"><b>{mb["n_words"]:,} → {ma["n_words"]:,}</b><span>Jumlah kata</span></div>',
            f'<div class="stat"><b>{len(r["integrity"])}</b><span>Peringatan integritas</span></div>',
            "</div>",
        ),
        unsafe_allow_html=True,
    )
    for n in r["notes"][1:]:
        st.caption("ℹ️ " + n)
    if r["integrity"]:
        st.warning(
            "Periksa sebelum dipakai:\n\n" + "\n".join(f"- {html.escape(msg)}" for _, msg in r["integrity"])
        )

    tabs = st.tabs(
        [
            "1. Revisi akhir",
            "2. Audit",
            "3. Keputusan diksi",
            "4. Poin konfirmasi",
            "5. Metrik sebelum/sesudah",
            "6. Draf & teks asli",
        ]
    )
    with tabs[0]:
        st.markdown(f'<div class="hz-text">{html.escape(r["final"])}</div>', unsafe_allow_html=True)
        with st.expander("Salin teks"):
            st.code(r["final"], language=None)
        stem = _safe_stem(name)
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "⬇️ Unduh revisi (.docx)",
                core.to_docx_bytes(f"Revisi: {name}", r["final"]),
                file_name=f"{stem}_humanized.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"hz_docx_{idx}",
            )
        with c2:
            st.download_button(
                "⬇️ Unduh revisi (.txt)",
                r["final"].encode("utf-8"),
                file_name=f"{stem}_humanized.txt",
                mime="text/plain",
                key=f"hz_txt_{idx}",
            )
    with tabs[1]:
        st.markdown("**Apa yang masih membuat teks terbaca sebagai tulisan AI atau terjemahan?**")
        if r["audit"]:
            st.markdown("\n".join(f"- {a}" for a in r["audit"]))
        else:
            st.write("Tidak ada temuan audit.")
        if r["perubahan"]:
            st.markdown("**Perubahan terpenting**")
            st.dataframe(
                pd.DataFrame(r["perubahan"], columns=["Kalimat asli", "Kalimat revisi", "Alasan (kode katalog)"]),
                hide_index=True,
            )
    with tabs[2]:
        if r["diksi"]:
            st.dataframe(
                pd.DataFrame(r["diksi"], columns=["Istilah lama", "Istilah baru", "Alasan", "Jumlah"]),
                hide_index=True,
            )
            st.caption("Keputusan istilah adalah wewenang penulis. Terapkan atau kembalikan secara konsisten di seluruh dokumen.")
        else:
            st.write("Tidak ada istilah yang diganti.")
    with tabs[3]:
        if r["konfirmasi"]:
            st.markdown("\n".join(f"- {k}" for k in r["konfirmasi"]))
        else:
            st.write("Tidak ada poin substansi yang perlu dikonfirmasi.")
        st.caption("Substansi (angka, klaim, sitasi, nomor tabel/gambar) tidak diubah diam-diam. Penulis yang memutuskan.")
    with tabs[4]:
        st.dataframe(pd.DataFrame(core.metrics_compare_rows(mb, ma)), hide_index=True)
        st.caption(
            f"Preset {r['register']}. Lulus seluruh metrik adalah syarat perlu, bukan syarat cukup: "
            "kalke dan personifikasi tidak terlihat oleh metrik."
        )
    with tabs[5]:
        st.markdown("**Draf (putaran pertama)**")
        st.markdown(f'<div class="hz-text">{html.escape(r["draft"])}</div>', unsafe_allow_html=True)
        st.markdown("**Teks asli**")
        st.markdown(f'<div class="hz-text">{html.escape(r["original"])}</div>', unsafe_allow_html=True)


SLIDES = [
    (
        "01",
        "Statistik lokal",
        "Dihitung langsung",
        "Variasi kalimat, kosakata, transisi, dan pola klise diukur langsung dari teks Anda.",
        ["ChatGPT", "Claude", "DeepSeek", "Gemini", "Copilot"],
        "rust",
        "black",
    ),
    (
        "02",
        "Penilaian AI",
        "Paham bahasa",
        "Aspek yang butuh pemahaman bahasa dinilai oleh model AI.",
        ["Grok", "Llama", "Mistral", "Qwen"],
        "black",
        "rust",
    ),
    (
        "03",
        "Transparan",
        "Tanpa kotak hitam",
        "Setiap parameter, skor, dan bobotnya bisa dilihat.",
        ["Kimi", "Perplexity", "Meta AI", "Dan lainnya"],
        "rust",
        "mist",
    ),
]


def slide_html(s):
    num, title, tag, desc, chips, left, right = s
    chip_html = "".join(f"<span>{c}</span>" for c in chips)
    return (
        f'<div class="slide"><div class="pn pn-{left}">'
        f'<span class="mono">Fitur {num} / 03</span>'
        f'<div><div class="slide-title">{title}</div><p class="slide-desc">{desc}</p>'
        f'<div class="chips">{chip_html}</div></div></div>'
        f'<div class="pn pn-{right} pn-num"><span class="mono">{tag} ↗</span>'
        f'<div class="slide-num">{num}</div></div></div>'
    )


SLIDER_HTML = (
    '<div class="slider"><div class="track">'
    + "".join(slide_html(s) for s in SLIDES + SLIDES[:1])
    + '</div><div class="dots"><i></i><i></i><i></i></div></div>'
)

_MQ = "".join(
    f"<span>{w}</span><i>/</i>"
    for w in ["ChatGPT", "Claude", "DeepSeek", "Gemini", "Copilot", "Grok", "Llama", "Mistral", "Qwen"]
)
MARQUEE_HTML = f'<div class="marquee"><div class="marquee-in">{_MQ}{_MQ}</div></div>'

NAV_HTML = (
    '<div class="nav"><a class="nav-brand" href="#" target="_self">Apeng<i>.</i></a><div class="nav-links">'
    '<a href="#fitur" target="_self">Fitur</a><a href="#humanizer" target="_self">Humanizer</a><a href="#cara-kerja" target="_self">Cara kerja</a>'
    '<a href="#perbandingan" target="_self">Perbandingan</a><a href="#faq" target="_self">FAQ</a></div>'
    '<a class="nav-cta" href="#mulai" target="_self">Mulai analisis</a></div>'
)


def sec_head(eyebrow, title, sub, sid):
    return (
        f'<div class="sec" id="{sid}"><div class="sec-eyebrow"><i></i>{eyebrow}</div>'
        f'<div class="sec-title">{title}</div><p class="sec-sub">{sub}</p></div>'
    )


STEPS = [
    ("Pilih sumber", "Unggah PDF/DOCX atau tempel teks langsung.", "", ""),
    ("Setujui", "Centang pemberitahuan keamanan data sebelum mulai.", "", ""),
    ("Hitung lokal", "Variasi kalimat, kosakata, transisi, dan klise dihitung di aplikasi.", "Lokal", "local"),
    ("Nilai AI", "Cuplikan awal, tengah, dan akhir dibaca model AI.", "AI", "ai"),
    ("Lihat skor", "Skor 0-100, checklist, kalimat mencurigakan, dan saran.", "", ""),
    ("Unduh", "Simpan ringkasan skor sebagai file CSV.", "CSV", ""),
]
STEPS_HTML = (
    '<div class="steps">'
    + "".join(
        f'<div class="step {k}"><div class="step-dot">{i}</div><div class="step-t">{t}</div><p>{d}</p>'
        + (f'<span class="step-tag">{tag}</span>' if tag else "")
        + "</div>"
        for i, (t, d, tag, k) in enumerate(STEPS, 1)
    )
    + "</div>"
)

CMP_COLS = ["Tebak manual", "Detektor satu-skor", "Apeng Detector"]
_Y, _N, _P = "y", "n", "p"
CMP_ROWS = [
    ("Skor diuraikan per parameter", [(_N, "✕", "Tidak ada"), (_N, "✕", "Umumnya tidak"), (_Y, "✓", "Ya, 38 indikator")]),
    ("Statistik terukur", [(_N, "✕", "Hanya perasaan"), (_P, "◐", "Tidak ditampilkan"), (_Y, "✓", "Dihitung langsung")]),
    ("Penilaian bahasa oleh AI", [(_P, "◐", "Subjektif"), (_P, "◐", "Tidak dijelaskan"), (_Y, "✓", "Disertai alasan")]),
    ("Kalimat yang dicurigai", [(_P, "◐", "Tergantung pembaca"), (_P, "◐", "Kadang"), (_Y, "✓", "Dikutip + alasan")]),
    ("Saran revisi", [(_P, "◐", "Tergantung pembaca"), (_N, "✕", "Jarang"), (_Y, "✓", "Ya")]),
    ("Teks Indonesia dan Inggris", [(_P, "◐", "Tergantung pembaca"), (_P, "◐", "Bervariasi"), (_Y, "✓", "Ya")]),
]
CMP_HTML = (
    '<div class="cmp-wrap"><table class="cmp"><thead><tr><th>Aspek</th>'
    + "".join(f'<th class="{"us" if i == 2 else ""}">{c}</th>' for i, c in enumerate(CMP_COLS))
    + "</tr></thead><tbody>"
    + "".join(
        "<tr><td>"
        + a
        + "</td>"
        + "".join(
            f'<td class="{c} {"us" if i == 2 else ""}"><b>{s}</b> {t}</td>' for i, (c, s, t) in enumerate(cells)
        )
        + "</tr>"
        for a, cells in CMP_ROWS
    )
    + "</tbody></table></div>"
    '<p class="cmp-note">* Perbandingan bersifat umum antar cara kerja, bukan penilaian produk tertentu. '
    "Hasil detektor adalah indikasi, bukan bukti mutlak.</p>"
)

_DATA_ANS = (
    "Uploaded or pasted documents will not be leaked, shared, or published. "
    "Files are processed solely during the analysis evaluation."
)

FAQS = [
    (
        "Apakah hasilnya pasti akurat?",
        "Tidak. Skor adalah indikasi berdasarkan statistik dan penilaian AI, bukan bukti. Jangan jadikan satu-satunya dasar keputusan.",
    ),
    ("Apakah dokumen saya aman dan rahasia?", _DATA_ANS),
    (
        "Bahasa dan format apa yang didukung?",
        "Teks berbahasa Indonesia dan Inggris, dalam file PDF atau Word (.docx), atau ditempel langsung. "
        "PDF hasil scan tanpa teks tidak bisa dibaca.",
    ),
    (
        "Berapa panjang teks yang ideal?",
        "Sekitar 200 kata atau lebih agar hasil stabil. Teks di bawah 50 kata dilewati. Hingga 10 file bisa diproses sekaligus.",
    ),
    (
        "Kenapa skornya bisa sedikit berbeda saat diulang?",
        "Bagian penilaian oleh AI bisa bervariasi tipis antar percobaan. Statistik lokal selalu sama untuk teks yang sama.",
    ),
    (
        "Apa itu mode Humanizer?",
        "Penyunting bahasa Indonesia berbasis skill Humanizer Indonesia. Ia membuang nominalisasi, konektor berlebih, "
        "kalke dari bahasa Inggris, dan ritme kalimat yang seragam, lalu menyerahkan draf, audit, keputusan diksi, "
        "poin konfirmasi, dan perbandingan metrik sebelum dan sesudah.",
    ),
    (
        "Apakah hasil Humanizer pasti lolos detektor AI?",
        "Tidak, dan memang bukan itu tujuannya. Teks yang disunting otomatis tetap dapat terdeteksi sebagai tulisan AI. "
        "Hasilnya adalah draf yang lebih enak dibaca untuk Anda sunting sendiri. Ungkapkan pemakaian AI jika diwajibkan.",
    ),
]
FAQ_HTML = (
    '<div class="faq">' + "".join(f"<details><summary>{q}</summary><p>{a}</p></details>" for q, a in FAQS) + "</div>"
)

# Deklarasi gabungan komponen komponen HTML landing page
HZ_FEATS = [
    ("Draf, audit, revisi", "Dua putaran: draf mengikuti katalog pola, lalu audit dan revisi akhir dengan metrik terbaru."),
    ("Kalke & diksi", "Kalimat terjemahan, personifikasi, dan pembuka monoton ditulis ulang, bukan sekadar diganti sinonim."),
    ("Angka tetap utuh", "Angka, rujukan gambar/tabel, dan sitasi diperiksa otomatis agar tidak ada yang hilang."),
    ("Transparan", "Keputusan diksi, poin konfirmasi, dan metrik sebelum-sesudah ditampilkan untuk Anda nilai."),
]
HUMANIZER_HTML = '<div class="hz-feat">' + "".join(f"<div><b>{t}</b><p>{d}</p></div>" for t, d in HZ_FEATS) + "</div>"

SECTIONS_HTML = html_block(
    sec_head(
        "Humanizer",
        "Rapikan bahasa, <em>bukan menyamarkan.</em>",
        "Pilih mode Humanizer di kotak analisis untuk menyunting teks bahasa Indonesia agar tidak kaku dan tidak terasa "
        "terjemahan. Hasilnya draf untuk Anda sunting, bukan alat untuk lolos detektor.",
        "humanizer",
    ),
    HUMANIZER_HTML,
    sec_head(
        "Cara kerja",
        "Enam langkah, dari berkas <em>sampai skor.</em>",
        "Setiap tahap transparan: Anda tahu mana yang dihitung langsung di aplikasi dan mana yang dinilai AI.",
        "cara-kerja",
    ),
    STEPS_HTML,
    sec_head(
        "Perbandingan",
        "Kenapa bukan <em>tebak-tebakan?</em>",
        "Menilai tulisan AI dengan perasaan sering meleset, dan satu angka tanpa penjelasan sulit dipertanggungjawabkan. "
        "Di sini setiap hitungan diperlihatkan.",
        "perbandingan",
    ),
    CMP_HTML,
    sec_head("FAQ", "Pertanyaan yang <em>sering muncul.</em>", "", "faq"),
    FAQ_HTML,
)


# ---------------- Tampilan Utama ----------------
st.markdown(
    html_block(
        NAV_HTML,
        '<div class="hero">',
        f'<span class="eyebrow">{html.escape(BADGE)}</span>',
        '<div class="hero-title">Apeng AI <em>Content Detector</em></div>',
        f'<div class="hero-sub">{html.escape(SUBTITLE)}</div>',
        MARQUEE_HTML,
        "</div>",
        '<div id="fitur"></div>',
        SLIDER_HTML,
    ),
    unsafe_allow_html=True,
)

default_key = server_key()
typed_key = ""

if not default_key:
    typed_key = st.text_input(
        "API key",
        type="password",
        placeholder="Masukkan API key layanan AI Anda",
        help="Key hanya dipakai selama sesi ini dan tidak disimpan.",
    )

api_key = typed_key or default_key

# Notice Keamanan & Kerahasiaan (Versi Bahasa Inggris)
st.info(
    "Privacy Notice: All uploaded or pasted files will not be leaked, shared, or published. "
    "Files are processed solely for analysis purposes."
)
agree = st.checkbox("I understand and agree to the processing of this document under these terms.")

st.markdown('<div class="section-title" id="mulai">Mulai analisis</div>', unsafe_allow_html=True)
try:
    card = st.container(border=True, key="main_card")
except TypeError:
    card = st.container(border=True)

with card:
    mode = st.radio(
        "Mode",
        ["🔎 AI Detector", "✍️ Humanizer"],
        horizontal=True,
        key="mode",
        label_visibility="collapsed",
    )
    is_hz = mode.endswith("Humanizer")
    if is_hz:
        st.markdown(f'<div class="hz-note">{html.escape(core.HUMANIZER_DISCLAIMER)}</div>', unsafe_allow_html=True)
        oc1, oc2 = st.columns(2)
        with oc1:
            hz_register = st.selectbox(
                "Register sasaran",
                list(core.HUMANIZER_REGISTERS),
                format_func=lambda k: core.HUMANIZER_REGISTERS[k],
                key="hz_register",
            )
        with oc2:
            hz_voice = st.selectbox(
                "Suara penulis",
                list(core.HUMANIZER_VOICES),
                format_func=lambda k: core.HUMANIZER_VOICES[k],
                key="hz_voice",
                help="Netral jika Anda tidak punya preset suara. Preset PRIB adalah contoh suara milik penulis skill.",
            )
        hz_english = st.checkbox(
            "Teks ini disusun dari sumber berbahasa Inggris (slide, laporan lembaga, standar)",
            key="hz_english",
        )
    tab_file, tab_text = st.tabs(["📎 Unggah file", "✍️ Tempel teks"])
    with tab_file:
        files = st.file_uploader(
            "PDF atau Word (.docx)", type=["pdf", "docx"], accept_multiple_files=True, label_visibility="collapsed"
        )
    with tab_text:
        pasted = st.text_area(
            "Tempel teks di sini (minimal ±200 kata)",
            height=220,
            placeholder="Tempel teks di sini (minimal ±200 kata)...",
            label_visibility="collapsed",
        )
    run = st.button("Humanize" if is_hz else "Analisis", type="primary")

if run:
    if not api_key:
        st.error("Masukkan API key terlebih dahulu.")
        st.stop()
    if not agree:
        st.error("Centang persetujuan keamanan dokumen terlebih dahulu.")
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

    pool = get_pool()
    drive_futs = []
    if DRIVE_ON:
        drive_futs = [(n, pool.submit(_bg_upload, n, d, m)) for n, d, m in uploads]

    client = anthropic.Anthropic(api_key=api_key)

    if is_hz:
        hz_todo = []
        for name, text in inputs:
            ok, why = core.humanize_eligibility(text)
            if not ok:
                st.warning(f"{name}: {why} Dilewati.")
                continue
            hz_todo.append((name, text))
        hz_results = []
        if hz_todo:
            with st.spinner(f"Menyunting {len(hz_todo)} dokumen (draf, audit, revisi akhir) ..."):
                with ThreadPoolExecutor(max_workers=2) as ex:
                    futs = [
                        (n, ex.submit(core.humanize, client, t, hz_register, hz_voice, hz_english))
                        for n, t in hz_todo
                    ]
                    for n, fu in futs:
                        try:
                            hz_results.append((n, fu.result()))
                        except Exception as e:
                            st.error(f"{n}: gagal disunting. {scrub(e)}")
        st.session_state["hz_results"] = hz_results
        if DRIVE_ON and drive_futs:
            wait([fu for _, fu in drive_futs], timeout=30)

    todo = []
    for name, text in ([] if is_hz else inputs):
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

    if not is_hz:
        st.session_state["results"] = results

    if DRIVE_ON and not is_hz:
        if results:
            pool.submit(_bg_upload, "hasil_deteksi.csv", summary_csv(results), "text/csv")
        if drive_futs:
            wait([fu for _, fu in drive_futs], timeout=30)

results = st.session_state.get("results", []) if not is_hz else []
if is_hz:
    hz_results = st.session_state.get("hz_results", [])
    if hz_results:
        st.divider()
        for i, (name, r) in enumerate(hz_results):
            render_humanize_result(name, r, i)
            st.divider()
if results:
    st.divider()
    for name, r in results:
        render_result(name, r)
        st.divider()
    st.download_button(
        "⬇️ Unduh ringkasan skor (CSV)", summary_csv(results), file_name="hasil_deteksi.csv", mime="text/csv"
    )

st.markdown(SECTIONS_HTML, unsafe_allow_html=True)

st.markdown(
    html_block(
        '<div class="fine">',
        (html.escape(core.DISCLAIMER) + "<br>") if (results or (is_hz and st.session_state.get("hz_results"))) else "",
        "All documents will not be leaked, shared, or published. Your files are processed solely for evaluation purposes.",
        "</div>",
    ),
    unsafe_allow_html=True,
)
