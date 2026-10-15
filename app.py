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
SUBTITLE = ("Periksa apakah sebuah tulisan kemungkinan dibuat AI. "
            "Statistik dihitung langsung, aspek yang butuh pemahaman bahasa dinilai oleh model AI.")

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
