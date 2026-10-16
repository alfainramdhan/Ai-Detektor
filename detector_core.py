import os
import re
import json
import statistics
from collections import Counter

MODEL = "claude-haiku-5-5"
MAX_CHARS_LLM = 30000
MIN_WORDS = 200

TRANSITIONS = [
    "selain itu", "oleh karena itu", "dengan demikian", "lebih lanjut", "di sisi lain",
    "pada akhirnya", "penting untuk dicatat", "namun demikian", "selanjutnya",
    "oleh sebab itu", "meskipun demikian", "dengan kata lain", "secara keseluruhan",
    "pada dasarnya", "sebagai contoh", "sebagai tambahan",
    "moreover", "furthermore", "additionally", "in addition", "therefore", "thus",
    "consequently", "on the other hand", "however", "nevertheless", "in conclusion",
    "overall", "it is important to note", "for instance", "as a result",
]

CLICHES = [
    "di era digital", "di era modern", "dalam dunia yang terus berkembang",
    "dapat disimpulkan bahwa", "tidak dapat dipungkiri", "seiring dengan perkembangan",
    "perlu dicatat bahwa", "penting untuk dicatat", "memainkan peran penting",
    "peran yang sangat penting", "di zaman sekarang",
    "in today's digital", "in today's fast-paced", "plays a crucial role",
    "play a crucial role", "plays a pivotal role", "it is important to note",
    "in conclusion", "delve into", "rapidly evolving", "ever-evolving",
    "a testament to", "in the realm of", "underscores the importance", "tapestry",
    "unlock the potential", "game-changer", "fostering a",
    "jujur saja", "bikin kepala mau pecah", "masalah paling klasik",
    "bukan cuma menampilkan", "bayangkan ada", "tapi jangan salah",
    "agak berlebihan", "hiasan layar belaka", "efisien banget", "di sinilah peran"
]

BOMBASTIC = {
    "krusial", "signifikan", "holistik", "komprehensif", "esensial", "dinamis",
    "inovatif", "optimal", "fundamental", "transformatif", "kokoh",
    "crucial", "pivotal", "holistic", "comprehensive", "seamless", "leverage",
    "leveraging", "significant", "innovative", "essential", "dynamic", "robust",
    "streamline", "paradigm", "synergy", "cutting-edge", "indispensable",
    "paramount", "multifaceted", "quintessential", "ubiquitous", "fundamentally",
    "herein", "thus", "hence",
}

TRANS_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(p) for p in sorted(TRANSITIONS, key=len, reverse=True)) + r")\b"
)

# 16 Parameter & Bobot
WEIGHTS = {
    "burstiness": 12,
    "perplexity": 12,
    "mtld": 4,
    "transisi": 8,
    "klise": 10,
    "bombastis": 6,
    "trigram": 4,
    "paragraf": 4,
    "dash": 4,
    "typo": 3,
    "personal": 5,
    "struktur": 5,
    "rhetorical": 5,
    "summary_closing": 4,
    "neutral_tone": 4,
    "awkward_synonyms": 5,
}

LABELS = {
    "burstiness": "Burstiness (variasi panjang kalimat)",
    "perplexity": "Perplexity (estimasi LLM)",
    "mtld": "Keragaman leksikal (MTLD)",
    "transisi": "Kata transisi per 100 kata",
    "klise": "Frasa klise per 1.000 kata",
    "bombastis": "Kata bombastis / hiper-formal per 100 kata",
    "trigram": "Pengulangan trigram (%, per 500 kata)",
    "paragraf": "Keseragaman panjang paragraf (CV)",
    "dash": "Tanda pisah panjang (—) per 1.000 kata",
    "typo": "Kesalahan ketik/ejaan (penilaian LLM)",
    "personal": "Detail personal & konkret (penilaian LLM)",
    "struktur": "Struktur dokumen sangat rapi/simetris (penilaian LLM)",
    "rhetorical": "Pola paralel & retoris (Not Only X But Y)",
    "summary_closing": "Penutup mengulang ringkasan isi",
    "neutral_tone": "Nada netral datar / diplomatik",
    "awkward_synonyms": "Sinonim kaku / parafrase dipaksa (QuillBot)",
}

CHECKLIST_LABELS = [
    ("burstiness_low", "Panjang kalimat seragam (CV < 0.35)"),
    ("perplexity_low", "Perplexity rendah (alur kata sangat tertebak)"),
    ("mtld_low", "Kosakata kurang beragam / sedang (MTLD < 80)"),
    ("transitions_high", "Kata transisi > 2.5 per 100 kata"),
    ("cliche_high", "Frasa klise >= 2.0 per 1.000 kata"),
    ("bombastic_high", "Kata bombastis/hiper-formal > 2.0 per 100 kata"),
    ("trigram_high", "Pengulangan trigram > 4.0% (per 500 kata)"),
    ("paragraph_cv_low", "Panjang paragraf seragam (CV < 0.35)"),
    ("zero_typo", "Nol kesalahan ketik/ejaan (100% steril)"),
    ("lack_personal_details", "Minim detail personal, pengalaman, dan contoh konkret"),
    ("overly_structured", "Struktur dokumen sangat rapi/simetris"),
    ("em_dash_high", "Tanda pisah panjang (—) > 2.0 per 1.000 kata"),
    ("rhetorical_patterns", "Pola 'bukan hanya X, tetapi juga Y' / tiga serangkai berulang"),
    ("repetitive_summary", "Penutup mengulang ringkasan isi"),
    ("neutral_tone", "Nada netral datar / gaya santai buatan"),
    ("opening_hook_cliche", "Pembuka klise (\"In today's rapidly evolving...\" / gaya santai buatan)"),
    ("hedge_words_high", "Dominasi kata pembatas risiko berlebih (appears to, tends to, arguably)"),
    ("explanatory_framing", "Format penjelas kaku/definisi otomatis di awal kalimat"),
    ("awkward_synonyms", "Kejanggalan pemilihan sinonim (QuillBot artifacts)"),
    ("forced_passive_active", "Restrukturisasi pasif/aktif yang dipaksa"),
    ("over_academic_connectors", "Konektor akademis hiper-formal (hence, herein, thus)"),
    ("cohesion_disparities", "Disparitas kohesi/penurunan alur narasi antar-paragraf"),
]

REF_HEADING = re.compile(r"(?im)^\s*(references|reference list|daftar pustaka|bibliography)\s*$")


def clean_text(pages):
    counts = Counter()
    for pg in pages:
        for ln in set(l.strip() for l in pg.splitlines() if l.strip()):
            counts[ln] += 1
    thr = max(3, int(len(pages) * 0.3))
    repeated = {ln for ln, c in counts.items() if c >= thr}
    kept = []
    for pg in pages:
        kept.append("\n".join(l for l in pg.splitlines() if l.strip() and l.strip() not in repeated))
    t = "\n".join(kept)
    t = re.sub(r"https?://\S+|www\.\S+|\S+@\S+", " ", t)
    refs = list(REF_HEADING.finditer(t))
    if refs and refs[-1].start() > len(t) * 0.5:
        t = t[:refs[-1].start()]
    return t.strip()


def extract_text(file_path):
    from pypdf import PdfReader
    from docx import Document

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        reader = PdfReader(file_path)
        return clean_text([(page.extract_text() or "") for page in reader.pages])
    if ext == ".docx":
        doc = Document(file_path)
        paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return clean_text(["\n\n".join(paras)])
    raise ValueError("Format tidak didukung. Gunakan PDF atau DOCX.")


def tokenize(text):
    return re.findall(r"[^\W\d_]+", text.lower())


def cv(values):
    if len(values) < 3:
        return None
    m = statistics.mean(values)
    return statistics.pstdev(values) / m if m else None


def split_sentences(text):
    flat = re.sub(r"\s+", " ", text)
    for abbr in ("et al.", "e.g.", "i.e.", "Fig.", "Eq.", "vs."):
        flat = flat.replace(abbr, abbr.replace(".", ""))
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(\[])", flat)
    return [s for s in parts if len(tokenize(s)) >= 3]


def mtld(tokens, threshold=0.72):
    def one_pass(toks):
        factors, types, count = 0.0, set(), 0
        for t in toks:
            count += 1
            types.add(t)
            if len(types) / count <= threshold:
                factors += 1
                types, count = set(), 0
        if count > 0:
            factors += (1 - len(types) / count) / (1 - threshold)
        return len(toks) / factors if factors > 0 else float(len(toks))

    if len(tokens) < 50:
        return None
    return (one_pass(tokens) + one_pass(tokens[::-1])) / 2


def compute_local(text):
    words = tokenize(text)
    n = len(words)
    low = text.lower().replace("’", "'")

    sent_lens = [len(tokenize(s)) for s in split_sentences(text)]
    tri_vals = []
    win = 500
    if n >= 150:
        starts = range(0, max(1, n - win + 1), win)
        for i in starts:
            ch = words[i:i + win]
            if len(ch) >= 3:
                tg = list(zip(ch, ch[1:], ch[2:]))
                tri_vals.append((len(tg) - len(set(tg))) / len(tg) * 100)
    paras = [p for p in re.split(r"\n\s*\n", text) if len(tokenize(p)) >= 5]
    wc = Counter(words)

    return {
        "n_words": n,
        "burstiness": cv(sent_lens),
        "avg_sentence": statistics.mean(sent_lens) if sent_lens else None,
        "mtld": mtld(words),
        "transisi": len(TRANS_RE.findall(low)) / n * 100 if n else None,
        "klise": sum(low.count(c) for c in CLICHES) / n * 1000 if n else None,
        "bombastis": sum(c for w, c in wc.items() if w in BOMBASTIC) / n * 100 if n else None,
        "trigram": statistics.mean(tri_vals) if tri_vals else None,
        "paragraf": cv([len(tokenize(p)) for p in paras]) if len(paras) >= 3 else None,
        "dash": text.count("—") / n * 1000 if n else None,
    }


def score_local(key, v):
    """
    0 = Mirip Manusia, 100 = Mirip AI.
    Dikalibrasi untuk toleransi dokumen akademis manusia:
    """
    if v is None:
        return None
        
    if key == "burstiness":
        return 100 if v < 0.35 else 60 if v < 0.48 else 0
        
    if key == "mtld":
        return 100 if v < 45 else 60 if v < 65 else 0
        
    if key == "transisi":
        return 100 if v > 3.0 else 50 if v > 1.8 else 0
        
    if key == "klise":
        return 100 if v >= 2.5 else 50 if v >= 1.0 else 0
        
    if key == "bombastis":
        return 100 if v > 2.5 else 50 if v > 1.2 else 0
        
    if key == "trigram":
        return 100 if v > 5.0 else 50 if v > 2.5 else 0
        
    if key == "paragraf":
        return 100 if v < 0.30 else 50 if v < 0.45 else 0
        
    if key == "dash":
        return 100 if v > 2.5 else 50 if v > 1.0 else 0
        
    return None


PROMPT = """Kamu adalah auditor dokumen yang menilai apakah sebuah teks kemungkinan ditulis/di-edit oleh AI atau alat rewriter.
Teks di bawah bisa berupa karya ilmiah, artikel akademis, atau tulisan bebas (Indonesia/Inggris).

PENTING UNTUK KALIBRASI KARYA MANUSIA:
- Tulisan akademis/ilmiah berkualitas tinggi karya manusia BIASANYA steril dari kesalahan ejaan/typo, sangat rapi, dan memakai tata bahasa formal. JANGAN menghukum karya ilmiah sebagai AI hanya karena tulisan tersebut steril/rapi!
- AI ditandai oleh: alur yang terlalu mudah ditebak (perplexity rendah), pola retoris generik yang diulang-ulang, penutup ringkasan yang kaku, serta tidak adanya bukti empiris spesifik.

Skala semua skor numerik: 0 = sangat mirip tulisan manusia, 100 = sangat mirip tulisan AI.

Evaluasi Parameter Numerik (0-100):
- perplexity_score: ESTIMASI seberapa mudah ditebak pilihan kata dan alur kalimat (100 = sangat generik/prediktif, 0 = tak terduga/kaya argumen khas manusia).
- typo_score: 0 jika steril/rapi (normal untuk jurnal/manusia), 0 jika ada typo organik manusia. Berikan skor 60+ HANYA jika ada pola kejanggalan sinonim paksaan alat rewriter.
- personal_detail_score: 100 jika argumen/anekdot bersifat rekaan AI tanpa data empiris/sitasi riil; 0 jika menyajikan fakta, data, referensi, atau pengalaman konkret yang spesifik.
- structure_score: 100 jika struktur simetris kaku berulang; 0 jika struktur ilmiah/narasi alami.
- rhetorical_score: 100 jika terdeteksi berulang pola retoris 'bukan hanya X, tetapi juga Y' atau gabungan 3 poin berurutan; 0 jika alami.
- summary_closing_score: 100 jika paragraf penutup mengulang ringkasan isi secara kaku; 0 jika alami.
- neutral_tone_score: 100 jika nada terasa buatan tanpa kedalaman argumen; 0 jika menyajikan argumen kritis manusia.
- awkward_synonyms_score: 100 jika terdeteksi kejanggalan sinonim/parafrase dipaksa khas QuillBot; 0 jika alami.

Evaluasi 22 Indikator Checklist Boolean (true/false):
- opening_hook_cliche: true jika diawali frasa pembuka klise generik AI ("In today's rapidly evolving...", "Jujur saja,...").
- hedge_words_high: true jika terdominasi kata kualifikasi berlebih (appears to, tends to, arguably).
- explanatory_framing: true jika menyajikan format penjelas kaku / definisi otomatis di awal kalimat.
- forced_passive_active: true jika terjadi restrukturisasi pasif/aktif yang dipaksa atau kaku.
- over_academic_connectors: true jika menyisipkan konektor akademis hiper-formal pada gagasan sederhana.
- cohesion_disparities: true jika alur/kohesi antar-paragraf terasa diprogram.

Serta kutipan dan saran:
- contoh: 2-3 kutipan PERSIS (maks 25 kata) dari teks yang paling kuat mengindikasikan AI, beserta alasan singkat (bahasa Indonesia). Jika tidak ada, kosongkan.
- saran: 2-4 kalimat saran agar tulisan terasa lebih alami (bahasa Indonesia).

Balas HANYA dengan JSON valid, tanpa teks lain dan tanpa markdown:
{
 "perplexity_score": 0, "typo_score": 0, "personal_detail_score": 0, "structure_score": 0,
 "rhetorical_score": 0, "summary_closing_score": 0, "neutral_tone_score": 0, "awkward_synonyms_score": 0,
 "opening_hook_cliche": false, "hedge_words_high": false, "explanatory_framing": false,
 "forced_passive_active": false, "over_academic_connectors": false, "cohesion_disparities": false,
 "contoh": [{"kutipan": "", "alasan": ""}], "saran": ""
}

TEKS:
---
<<TEKS>>
---"""


def ask_claude(client, text):
    import anthropic

    sample = text[:MAX_CHARS_LLM]
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            messages=[{"role": "user", "content": PROMPT.replace("<<TEKS>>", sample)}],
        )
    except anthropic.APIStatusError as e:
        raise RuntimeError(f"Error API ({e.status_code}): {e.message}") from e

    out = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        raise RuntimeError("Claude tidak mengembalikan JSON:\n" + out[:500])
    return json.loads(m.group(0))


def clamp(x):
    try:
        return max(0, min(100, int(round(float(x)))))
    except (TypeError, ValueError):
        return None


def category(total):
    if total <= 25.0:
        return "Sangat Mungkin Manusia"
    if total <= 50.0:
        return "Kemungkinan Besar Manusia"
    if total <= 75.0:
        return "Indikasi Campuran / AI-Parafrase"
    return "Sangat Mungkin Dibuat AI"


def checklist_category(n_yes, n_valid):
    pct = (n_yes / n_valid * 100) if n_valid > 0 else 0
    if pct <= 20:
        return "Dominan Alami / Manusia"
    if pct <= 45:
        return "Indikasi Ringan AI"
    if pct <= 70:
        return "Indikasi Sedang / AI-Parafrase"
    return "Indikasi Kuat AI"


def _fmt(v, nd=2):
    return "n/a" if v is None else f"{v:.{nd}f}"


def evaluate(client, text):
    loc = compute_local(text)
    llm = ask_claude(client, text)

    scores = {
        k: score_local(k, loc.get(k))
        for k in ("burstiness", "mtld", "transisi", "klise", "bombastis", "trigram", "paragraf", "dash")
    }
    scores["perplexity"] = clamp(llm.get("perplexity_score"))
    scores["typo"] = clamp(llm.get("typo_score"))
    scores["personal"] = clamp(llm.get("personal_detail_score"))
    scores["struktur"] = clamp(llm.get("structure_score"))
    scores["rhetorical"] = clamp(llm.get("rhetorical_score"))
    scores["summary_closing"] = clamp(llm.get("summary_closing_score"))
    scores["neutral_tone"] = clamp(llm.get("neutral_tone_score"))
    scores["awkward_synonyms"] = clamp(llm.get("awkward_synonyms_score"))

    # Peta 22 Checklist Indikator
    def yn(cond):
        return None if cond is None else bool(cond)

    check_dict = {
        "burstiness_low": yn(None if loc["burstiness"] is None else loc["burstiness"] < 0.35),
        "perplexity_low": yn(None if scores["perplexity"] is None else scores["perplexity"] >= 60),
        "mtld_low": yn(None if loc["mtld"] is None else loc["mtld"] < 65),
        "transitions_high": yn(None if loc["transisi"] is None else loc["transisi"] > 2.5),
        "cliche_high": yn(None if loc["klise"] is None else loc["klise"] >= 2.0),
        "bombastic_high": yn(None if loc["bombastis"] is None else loc["bombastis"] > 2.0),
        "trigram_high": yn(None if loc["trigram"] is None else loc["trigram"] > 4.0),
        "paragraph_cv_low": yn(None if loc["paragraf"] is None else loc["paragraf"] < 0.35),
        "zero_typo": yn(None if scores["typo"] is None else scores["typo"] >= 80),
        "lack_personal_details": yn(None if scores["personal"] is None else scores["personal"] >= 60),
        "overly_structured": yn(None if scores["struktur"] is None else scores["struktur"] >= 70),
        "em_dash_high": yn(None if loc["dash"] is None else loc["dash"] > 2.0),
        "rhetorical_patterns": yn(None if scores["rhetorical"] is None else scores["rhetorical"] >= 50),
        "repetitive_summary": yn(None if scores["summary_closing"] is None else scores["summary_closing"] >= 50),
        "neutral_tone": yn(None if scores["neutral_tone"] is None else scores["neutral_tone"] >= 50),
        "opening_hook_cliche": yn(llm.get("opening_hook_cliche")),
        "hedge_words_high": yn(llm.get("hedge_words_high")),
        "explanatory_framing": yn(llm.get("explanatory_framing")),
        "awkward_synonyms": yn(None if scores["awkward_synonyms"] is None else scores["awkward_synonyms"] >= 50),
        "forced_passive_active": yn(llm.get("forced_passive_active")),
        "over_academic_connectors": yn(llm.get("over_academic_connectors")),
        "cohesion_disparities": yn(llm.get("cohesion_disparities")),
    }

    items = [(label, check_dict.get(key)) for key, label in CHECKLIST_LABELS]
    n_yes = sum(1 for _, a in items if a is True)
    n_valid = sum(1 for _, a in items if a is not None)

    # Rumus Hitung Gabungan
    avail = {k: w for k, w in WEIGHTS.items() if scores.get(k) is not None}
    weighted_sum = sum(scores[k] * w for k, w in avail.items()) / sum(avail.values()) if avail else 0.0
    checklist_penalty = (n_yes / n_valid * 20.0) if n_valid > 0 else 0.0
    raw_total = weighted_sum + checklist_penalty

    # =========================================================================
    # KALIBRASI MANUSIA (HUMAN SAFETY BUFFER):
    # Jika checklist "Ya" <= 2 ATAU tulisan memiliki variasi kaya (MTLD >= 65 & Burstiness >= 0.45),
    # redam skor mentah hingga maksimal 0.0% - 4.9%.
    # =========================================================================
    if n_yes <= 2 or (loc.get("mtld") and loc["mtld"] >= 65 and loc.get("burstiness") and loc["burstiness"] >= 0.45):
        total = round(min(4.9, (raw_total / 30.0) * 4.9), 1)
    else:
        total = min(100.0, raw_total)

    shown = {
        "burstiness": _fmt(loc["burstiness"]),
        "perplexity": "-",
        "mtld": _fmt(loc["mtld"], 1),
        "transisi": _fmt(loc["transisi"]),
        "klise": _fmt(loc["klise"]),
        "bombastis": _fmt(loc["bombastis"]),
        "trigram": _fmt(loc["trigram"]),
        "paragraf": _fmt(loc["paragraf"]),
        "dash": _fmt(loc["dash"]),
        "typo": "-",
        "personal": "-",
        "struktur": "-",
        "rhetorical": "-",
        "summary_closing": "-",
        "neutral_tone": "-",
        "awkward_synonyms": "-",
    }

    rows = []
    for k, w in WEIGHTS.items():
        sc = scores.get(k)
        rows.append({
            "key": k,
            "parameter": LABELS[k],
            "nilai": shown[k],
            "skor": sc,
            "bobot": w,
            "kontribusi": None if sc is None else round(sc * w / 100, 1),
        })

    notes = []
    if loc["n_words"] < MIN_WORDS:
        notes.append(f"Teks kurang dari {MIN_WORDS} kata, hasil kurang stabil.")
    if len(text) > MAX_CHARS_LLM:
        notes.append(
            f"Penilaian LLM memakai {MAX_CHARS_LLM:,} karakter pertama dari {len(text):,}. Statistik lokal memakai seluruh teks."
        )
    if len(avail) < len(WEIGHTS):
        notes.append("Parameter n/a dikeluarkan dan bobot sisanya dinormalisasi ulang.")

    return {
        "n_words": loc["n_words"],
        "avg_sentence": loc["avg_sentence"],
        "n_chars": len(text),
        "rows": rows,
        "total": total,
        "category": category(total),
        "checklist": items,
        "n_yes": n_yes,
        "n_valid": n_valid,
        "checklist_category": checklist_category(n_yes, n_valid),
        "contoh": llm.get("contoh") or [],
        "saran": llm.get("saran", "-"),
        "notes": notes,
    }


DISCLAIMER = "Dibuat khusus Teman Teman Apeng."
