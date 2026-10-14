import os
import re
import json
import statistics
from collections import Counter

MODEL = "claude-haiku-5-5"
MAX_CHARS_LLM = 30000
MIN_WORDS = 300

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
]
BOMBASTIC = {
    "krusial", "signifikan", "holistik", "komprehensif", "esensial", "dinamis",
    "inovatif", "optimal", "fundamental", "transformatif", "kokoh",
    "crucial", "pivotal", "holistic", "comprehensive", "seamless", "leverage",
    "leveraging", "significant", "innovative", "essential", "dynamic", "robust",
    "streamline", "paradigm", "synergy", "cutting-edge",
}

TRANS_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(p) for p in sorted(TRANSITIONS, key=len, reverse=True)) + r")\b"
)

WEIGHTS = {
    "burstiness": 20, "perplexity": 15, "mtld": 4, "transisi": 15, "klise": 15,
    "bombastis": 8, "trigram": 3, "paragraf": 5, "typo": 2, "personal": 4,
    "struktur": 5, "dash": 4,
}
LABELS = {
    "burstiness": "Burstiness (variasi panjang kalimat)",
    "perplexity": "Perplexity (ESTIMASI Claude)",
    "mtld": "Keragaman leksikal (MTLD)",
    "transisi": "Kata transisi per 100 kata",
    "klise": "Frasa klise per 1.000 kata",
    "bombastis": "Kata bombastis per 100 kata",
    "trigram": "Pengulangan trigram (%, per 500 kata)",
    "paragraf": "Keseragaman panjang paragraf (CV)",
    "typo": "Kesalahan ketik/ejaan (Claude)",
    "personal": "Detail personal/konkret (Claude)",
    "struktur": "Struktur dokumen terlalu rapi (Claude)",
    "dash": "Tanda pisah panjang (—) per 1.000 kata",
}

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
    if n >= 200:
        starts = range(0, n - win + 1, win) if n >= win else [0]
        for i in starts:
            ch = words[i:i + win]
            tg = list(zip(ch, ch[1:], ch[2:]))
            tri_vals.append((len(tg) - len(set(tg))) / len(tg) * 100)
    paras = [p for p in re.split(r"\n\s*\n", text) if len(tokenize(p)) >= 10]
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
        "paragraf": cv([len(tokenize(p)) for p in paras]) if len(paras) >= 5 else None,
        "dash": text.count("—") / n * 1000 if n else None,
    }


def score_local(key, v):
    if v is None:
        return None
    if key == "burstiness":
        return 100 if v < 0.25 else 60 if v < 0.38 else 30 if v < 0.48 else 0
    if key == "mtld":
        return 100 if v < 45 else 60 if v < 65 else 30 if v < 85 else 0
    if key == "transisi":
        return 100 if v > 4 else 70 if v > 2.5 else 30 if v > 1 else 0
    if key == "klise":
        return 100 if v > 5 else 70 if v >= 3 else 30 if v >= 1 else 0
    if key == "bombastis":
        return 100 if v > 3 else 60 if v > 1.5 else 30 if v > 0.5 else 0
    if key == "trigram":
        return 100 if v > 6 else 60 if v > 4 else 30 if v > 3 else 0
    if key == "paragraf":
        return 100 if v < 0.2 else 60 if v < 0.35 else 30 if v < 0.5 else 0
    if key == "dash":
        return 100 if v > 5 else 60 if v >= 2 else 30 if v > 0 else 0
    return None


PROMPT = """Kamu adalah auditor dokumen yang menilai apakah sebuah teks kemungkinan ditulis AI.
Teks di bawah bisa berbahasa Indonesia atau Inggris. Nilai HANYA aspek berikut berdasarkan teks itu.
Skala semua skor: 0 = sangat mirip tulisan manusia, 100 = sangat mirip tulisan AI.

- perplexity_score: ESTIMASI seberapa mudah ditebak pilihan kata dan alur kalimat (100 = sangat generik/prediktif, 0 = tak terduga/khas manusia). Ini estimasi, bukan perplexity sebenarnya.
- typo_score: 100 jika nol kesalahan ketik/ejaan; 60 jika 1-2 per 1.000 kata; 30 jika 3-5; 0 jika lebih dari 5.
- personal_detail_score: 100 jika tidak ada detail personal/konkret (nama, tanggal, anekdot, pengalaman); 60 jika sedikit; 30 jika cukup; 0 jika banyak.
- structure_score: 100 jika struktur sangat rapi dan simetris (pembuka-poin-kesimpulan, bullet seragam); 60 rapi; 30 sedang; 0 tidak beraturan.
- pola_kontras_atau_tiga_serangkai: true jika pola "bukan hanya X, tetapi juga Y" / "not only X but also Y" atau daftar tiga serangkai muncul berulang.
- penutup_mengulang_ringkasan: true jika paragraf penutup hanya mengulang ringkasan isi.
- nada_netral_datar: true jika nada netral datar tanpa opini atau emosi.
- contoh: 2-3 kutipan PERSIS (maks 25 kata) dari teks yang paling kuat mengindikasikan AI, beserta alasan singkat (bahasa Indonesia). Jika tidak ada, kosongkan.
- saran: 2-4 kalimat saran agar tulisan terasa lebih alami (bahasa Indonesia).

Balas HANYA dengan JSON valid, tanpa teks lain dan tanpa markdown, dengan format:
{"perplexity_score": 0, "typo_score": 0, "personal_detail_score": 0, "structure_score": 0,
 "pola_kontras_atau_tiga_serangkai": false, "penutup_mengulang_ringkasan": false,
 "nada_netral_datar": false, "contoh": [{"kutipan": "", "alasan": ""}], "saran": ""}

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
    if total <= 25:
        return "Kemungkinan besar ditulis manusia"
    if total <= 50:
        return "Cenderung manusia / campuran"
    if total <= 75:
        return "Cenderung AI / campuran"
    return "Kemungkinan besar ditulis AI"


def checklist_category(n_yes):
    if n_yes <= 4:
        return "Kemungkinan besar manusia"
    if n_yes <= 8:
        return "Campuran / tidak pasti"
    if n_yes <= 11:
        return "Cenderung AI"
    return "Kemungkinan besar AI"


def _fmt(v, nd=2):
    return "n/a" if v is None else f"{v:.{nd}f}"


def evaluate(client, text):
    loc = compute_local(text)
    llm = ask_claude(client, text)

    scores = {k: score_local(k, loc.get(k)) for k in
              ("burstiness", "mtld", "transisi", "klise", "bombastis", "trigram", "paragraf", "dash")}
    scores["perplexity"] = clamp(llm.get("perplexity_score"))
    scores["typo"] = clamp(llm.get("typo_score"))
    scores["personal"] = clamp(llm.get("personal_detail_score"))
    scores["struktur"] = clamp(llm.get("structure_score"))

    avail = {k: w for k, w in WEIGHTS.items() if scores.get(k) is not None}
    total = sum(scores[k] * w for k, w in avail.items()) / sum(avail.values())

    shown = {
        "burstiness": _fmt(loc["burstiness"]), "perplexity": "-", "mtld": _fmt(loc["mtld"], 1),
        "transisi": _fmt(loc["transisi"]), "klise": _fmt(loc["klise"]), "bombastis": _fmt(loc["bombastis"]),
        "trigram": _fmt(loc["trigram"]), "paragraf": _fmt(loc["paragraf"]), "typo": "-",
        "personal": "-", "struktur": "-", "dash": _fmt(loc["dash"]),
    }
    rows = []
    for k, w in WEIGHTS.items():
        sc = scores.get(k)
        rows.append({
            "key": k, "parameter": LABELS[k], "nilai": shown[k], "skor": sc, "bobot": w,
            "kontribusi": None if sc is None else round(sc * w / 100, 1),
        })

    def yn(cond):
        return None if cond is None else bool(cond)

    items = [
        ("Panjang kalimat seragam (CV < 0,35)", yn(None if loc["burstiness"] is None else loc["burstiness"] < 0.35)),
        ("Perplexity rendah (estimasi)", yn(None if scores["perplexity"] is None else scores["perplexity"] >= 70)),
        ("Kosakata kurang beragam (MTLD < 65)", yn(None if loc["mtld"] is None else loc["mtld"] < 65)),
        ("Kata transisi > 2,5 per 100 kata", yn(None if loc["transisi"] is None else loc["transisi"] > 2.5)),
        ("Frasa klise >= 3 per 1.000 kata", yn(None if loc["klise"] is None else loc["klise"] >= 3)),
        ("Kata bombastis > 1,5 per 100 kata", yn(None if loc["bombastis"] is None else loc["bombastis"] > 1.5)),
        ("Pengulangan trigram > 4% (per 500 kata)", yn(None if loc["trigram"] is None else loc["trigram"] > 4)),
        ("Panjang paragraf seragam (CV < 0,35)", yn(None if loc["paragraf"] is None else loc["paragraf"] < 0.35)),
        ("Nol kesalahan ketik/ejaan", yn(None if scores["typo"] is None else scores["typo"] >= 100)),
        ("Minim detail personal dan konkret", yn(None if scores["personal"] is None else scores["personal"] >= 60)),
        ("Struktur dokumen sangat rapi/simetris", yn(None if scores["struktur"] is None else scores["struktur"] >= 100)),
        ("Tanda pisah panjang (—) > 2 per 1.000 kata", yn(None if loc["dash"] is None else loc["dash"] > 2)),
        ("Pola 'bukan hanya X, tetapi juga Y' / tiga serangkai berulang", yn(llm.get("pola_kontras_atau_tiga_serangkai"))),
        ("Penutup mengulang ringkasan isi", yn(llm.get("penutup_mengulang_ringkasan"))),
        ("Nada netral datar tanpa opini/emosi", yn(llm.get("nada_netral_datar"))),
    ]
    n_yes = sum(1 for _, a in items if a)
    n_valid = sum(1 for _, a in items if a is not None)

    notes = []
    if loc["n_words"] < MIN_WORDS:
        notes.append(f"Teks kurang dari {MIN_WORDS} kata, hasil kurang stabil.")
    if len(text) > MAX_CHARS_LLM:
        notes.append(f"Penilaian Claude memakai {MAX_CHARS_LLM:,} karakter pertama dari {len(text):,}. "
                     "Statistik lokal memakai seluruh teks.")
    if len(avail) < len(WEIGHTS):
        notes.append("Parameter n/a dikeluarkan dan bobot sisanya dinormalisasi ulang.")

    return {
        "n_words": loc["n_words"], "avg_sentence": loc["avg_sentence"], "n_chars": len(text),
        "rows": rows, "total": total, "category": category(total),
        "checklist": items, "n_yes": n_yes, "n_valid": n_valid,
        "checklist_category": checklist_category(n_yes),
        "contoh": llm.get("contoh") or [], "saran": llm.get("saran", "-"), "notes": notes,
    }


DISCLAIMER = ("Dibuat khusus Teman Teman Apeng.")
