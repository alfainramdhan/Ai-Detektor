import os
import io
import re
import time
import html
import tempfile

import pandas as pd
import streamlit as st
import anthropic

import detector_core as core

MAX_FILES = 10

# --- teks yang bisa Anda ubah ---
BADGE = "this application was made specifically for Apeng's Friends"
SUBTITLE = ("Periksa apakah sebuah tulisan kemungkinan dibuat AI. "
            "Statistik dihitung langsung, aspek yang butuh pemahaman bahasa dinilai oleh model AI.")

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
div[data-testid="stVerticalBlockBorderWrapper"],
