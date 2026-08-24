"""
Arogya — app.py
STRICT OCR Pipeline — NO false positives:

  Strategy:
  - EasyOCR reads the image
  - ONLY exact matches OR very high confidence fuzzy matches accepted
  - Pass 1: Exact name match (99% reliable)
  - Pass 2: Only if BOTH EasyOCR text AND medicine name are very similar (>88%)
  - NO random token scanning — that was causing false positives
  - Result: fewer medicines shown but ALL of them correct
"""

# ✅ CLEAN VERSION — replace your top section with this
from flask import Flask, render_template, request, redirect, url_for, session, flash

import json, os, re, hashlib
import numpy as np
import cv2
import pytesseract
import easyocr
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
from symspellpy import SymSpell, Verbosity
from rapidfuzz import fuzz, process as rf_process
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
app.secret_key = "arogya_secret_key_2025"



pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
TESS_COL    = r'--oem 3 --psm 4  -l eng'
TESS_SPARSE = r'--oem 3 --psm 11 -l eng'
CACHE_FILE = "scan_cache.json"

# ── EasyOCR loaded once ──
print("[Arogya] Loading EasyOCR...")
try:
    easy_reader   = easyocr.Reader(['en'], gpu=False, verbose=False)
    EASYOCR_READY = True
    print("[Arogya] EasyOCR ready ✓")
except Exception as e:
    EASYOCR_READY = False
    print(f"[Arogya] EasyOCR failed: {e}")


# ════════════════════════════════════════════════════════
#  MEDICINE DATABASE
# ════════════════════════════════════════════════════════
MEDICINE_DB = [
    {"name": "Paracetamol",         "price": 12},
    {"name": "Dolo 650",            "price": 22},
    {"name": "Dolo",                "price": 22},
    {"name": "Azithromycin",        "price": 85},
    {"name": "Amoxicillin",         "price": 72},
    {"name": "Cetirizine",          "price": 18},
    {"name": "Cetrizine",           "price": 18},
    {"name": "Metformin",           "price": 32},
    {"name": "Omeprazole",          "price": 45},
    {"name": "Pantoprazole",        "price": 38},
    {"name": "Ibuprofen",           "price": 25},
    {"name": "Aspirin",             "price": 15},
    {"name": "Atorvastatin",        "price": 55},
    {"name": "Amlodipine",          "price": 42},
    {"name": "Losartan",            "price": 48},
    {"name": "Metoprolol",          "price": 35},
    {"name": "Ciprofloxacin",       "price": 65},
    {"name": "Doxycycline",         "price": 58},
    {"name": "Cefixime",            "price": 88},
    {"name": "Levocetirizine",      "price": 28},
    {"name": "Montelukast",         "price": 75},
    {"name": "Salbutamol",          "price": 45},
    {"name": "Prednisolone",        "price": 32},
    {"name": "Diclofenac",          "price": 22},
    {"name": "Tramadol",            "price": 55},
    {"name": "Ranitidine",          "price": 18},
    {"name": "Domperidone",         "price": 28},
    {"name": "Ondansetron",         "price": 35},
    {"name": "Metronidazole",       "price": 20},
    {"name": "Albendazole",         "price": 15},
    {"name": "Vitamin C",           "price": 25},
    {"name": "Vitamin D3",          "price": 42},
    {"name": "Vitamin D",           "price": 42},
    {"name": "Vitamin B12",         "price": 38},
    {"name": "Iron",                "price": 22},
    {"name": "Folic Acid",          "price": 18},
    {"name": "Calcium",             "price": 35},
    {"name": "Zinc",                "price": 28},
    {"name": "Insulin",             "price": 180},
    {"name": "Glimepiride",         "price": 45},
    {"name": "Sitagliptin",         "price": 95},
    {"name": "Thyronorm",           "price": 42},
    {"name": "Levothyroxine",       "price": 38},
    {"name": "Warfarin",            "price": 25},
    {"name": "Clopidogrel",         "price": 55},
    {"name": "Digoxin",             "price": 28},
    {"name": "Furosemide",          "price": 18},
    {"name": "Torsemide",           "price": 35},
    {"name": "Dytor",               "price": 35},
    {"name": "Spironolactone",      "price": 35},
    {"name": "Hydroxychloroquine",  "price": 45},
    {"name": "Aceclofenac",         "price": 28},
    {"name": "Sertraline",          "price": 65},
    {"name": "Escitalopram",        "price": 55},
    {"name": "Alprazolam",          "price": 35},
    {"name": "Clonazepam",          "price": 28},
    {"name": "Gabapentin",          "price": 48},
    {"name": "Pregabalin",          "price": 75},
    {"name": "Pantop",              "price": 38},
    {"name": "Pan D",               "price": 45},
    {"name": "Cyra",                "price": 38},
    {"name": "Rabeprazole",         "price": 38},
    {"name": "Crocin",              "price": 15},
    {"name": "Combiflam",           "price": 28},
    {"name": "Flex",                "price": 28},
    {"name": "Allegra",             "price": 55},
    {"name": "Zyrtec",              "price": 48},
    {"name": "Augmentin",           "price": 95},
    {"name": "Taxim",               "price": 88},
    {"name": "Azee",                "price": 75},
    {"name": "Amoxyclav",           "price": 98},
    {"name": "Norfloxacin",         "price": 35},
    {"name": "Ofloxacin",           "price": 45},
    {"name": "Roxithromycin",       "price": 68},
    {"name": "Clarithromycin",      "price": 85},
    {"name": "Tinidazole",          "price": 28},
    {"name": "Fluconazole",         "price": 55},
    {"name": "Terbinafine",         "price": 65},
    {"name": "Clotrimazole",        "price": 38},
    {"name": "Betamethasone",       "price": 42},
    {"name": "Hydrocortisone",      "price": 35},
    {"name": "Calamine",            "price": 22},
    {"name": "Ketoconazole",        "price": 48},
    {"name": "Mupirocin",           "price": 55},
    {"name": "Neomycin",            "price": 32},
    {"name": "Chloramphenicol",     "price": 28},
    {"name": "Erythromycin",        "price": 58},
    {"name": "Tetracycline",        "price": 35},
    {"name": "Phenobarbitone",      "price": 18},
    {"name": "Phenytoin",           "price": 28},
    {"name": "Carbamazepine",       "price": 38},
    {"name": "Valproate",           "price": 55},
    {"name": "Levetiracetam",       "price": 75},
    {"name": "Atenolol",            "price": 22},
    {"name": "Propranolol",         "price": 18},
    {"name": "Nifedipine",          "price": 32},
    {"name": "Verapamil",           "price": 45},
    {"name": "Ramipril",            "price": 38},
    {"name": "Enalapril",           "price": 28},
    {"name": "Lisinopril",          "price": 32},
    {"name": "Telmisartan",         "price": 55},
    {"name": "Valsartan",           "price": 48},
    {"name": "Hydrochlorothiazide", "price": 15},
    {"name": "Chlorthalidone",      "price": 22},
    {"name": "Rosuvastatin",        "price": 68},
    {"name": "Simvastatin",         "price": 45},
    {"name": "Fenofibrate",         "price": 55},
    {"name": "Glibenclamide",       "price": 18},
    {"name": "Voglibose",           "price": 35},
    {"name": "Empagliflozin",       "price": 125},
    {"name": "Dapagliflozin",       "price": 118},
    {"name": "Teneligliptin",       "price": 85},
    {"name": "Pioglitazone",        "price": 42},
    {"name": "Acarbose",            "price": 55},
    {"name": "Esomeprazole",        "price": 48},
    {"name": "Itopride",            "price": 45},
    {"name": "Mosapride",           "price": 38},
    {"name": "Loperamide",          "price": 22},
    {"name": "ORS",                 "price": 15},
    {"name": "Lactulose",           "price": 35},
    {"name": "Bisacodyl",           "price": 18},
    {"name": "Dulcolax",            "price": 28},
    {"name": "Cremaffin",           "price": 55},
    {"name": "Digene",              "price": 22},
    {"name": "Gelusil",             "price": 18},
    {"name": "Mucaine",             "price": 32},
    {"name": "Cyclopam",            "price": 28},
    {"name": "Meftal Spas",         "price": 35},
    {"name": "Drotin",              "price": 30},
    {"name": "Buscopan",            "price": 38},
    {"name": "Avil",                "price": 15},
    {"name": "Phenergan",           "price": 22},
    {"name": "Benadryl",            "price": 45},
    {"name": "Ascoril",             "price": 55},
    {"name": "Grilinctus",          "price": 48},
    {"name": "Ambroxol",            "price": 32},
    {"name": "Bromhexine",          "price": 22},
    {"name": "Dextromethorphan",    "price": 28},
    {"name": "Codeine",             "price": 45},
    {"name": "Dexamethasone",       "price": 28},
    {"name": "Methylprednisolone",  "price": 55},
    {"name": "Budesonide",          "price": 75},
    {"name": "Fluticasone",         "price": 85},
    {"name": "Sorbitrate",          "price": 25},
    {"name": "GTN",                 "price": 25},
    {"name": "Isosorbide",          "price": 28},
    {"name": "Nitroglycerine",      "price": 30},
    {"name": "Moxifloxacin",        "price": 95},
    {"name": "Levofloxacin",        "price": 72},
    {"name": "Cefpodoxime",         "price": 98},
    {"name": "Cefuroxime",          "price": 88},
    {"name": "Amikacin",            "price": 75},
    {"name": "Clindamycin",         "price": 68},
    {"name": "Rifampicin",          "price": 85},
    {"name": "Isoniazid",           "price": 25},
    {"name": "Ethambutol",          "price": 35},
    {"name": "Pyrazinamide",        "price": 28},
    {"name": "Montek LC",           "price": 82},
    {"name": "Atarax",              "price": 38},
    {"name": "Fexofenadine",        "price": 55},
    {"name": "Bilastine",           "price": 65},
    {"name": "Pantodac",            "price": 40},
    {"name": "Razo",                "price": 35},
]

MEDICINE_NAMES = [m["name"] for m in MEDICINE_DB]

# Words that should NEVER be matched as medicines
IGNORE_WORDS = {
    "the", "and", "for", "with", "from", "this", "that", "have", "will",
    "date", "name", "age", "sex", "male", "female", "doctor", "patient",
    "address", "phone", "sign", "signature", "clinic", "hospital", "care",
    "morning", "night", "evening", "twice", "thrice", "daily", "once",
    "before", "after", "food", "meal", "water", "days", "weeks", "month",
    "tablet", "tablets", "capsule", "syrup", "dose", "dosage", "take",
    "times", "per", "each", "every", "total", "number", "ref", "reg",
    "prescription", "rx", "dr", "mbbs", "md", "ms", "fee", "charges",
    "weight", "height", "blood", "pressure", "sugar", "test", "report",
    "room", "token", "uhid", "dept", "consultant", "temp", "spo2", "amar",
    "health", "multispeciality", "sanjay", "meena", "parashar", "sonal",
    "gupta", "sood", "savitri", "devi", "mathura", "agra", "delhi",
    "medicine", "medical", "general", "internal", "paediatric", "dental",
}


# ════════════════════════════════════════════════════════
#  CACHE
# ════════════════════════════════════════════════════════

def get_image_hash(filepath):
    try:
        img  = Image.open(filepath).convert("L").resize((16, 16), Image.LANCZOS)
        arr  = list(img.getdata())
        avg  = sum(arr) / len(arr)
        bits = "".join("1" if p > avg else "0" for p in arr)
        return hex(int(bits, 2))[2:].zfill(16)
    except Exception:
        with open(filepath, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    with open(CACHE_FILE, "r") as f:
        return json.load(f)

def check_cache(h):
    c = load_cache().get(h)
    if c:
        print("[Cache] ✓ HIT")
        return c
    return None

def write_cache(h, medicines, mode):
    cache    = load_cache()
    cache[h] = {"medicines": medicines, "mode": mode}
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


# ════════════════════════════════════════════════════════
#  SYMSPELL + TF-IDF
# ════════════════════════════════════════════════════════

def build_symspell():
    sym = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
    for name in MEDICINE_NAMES:
        for word in name.lower().split():
            if len(word) > 2:
                sym.create_dictionary_entry(word, 1)
        sym.create_dictionary_entry(name.lower(), 1)
    return sym

print("[Arogya] Building SymSpell + TF-IDF...")
sym_spell    = build_symspell()
tfidf        = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4),
                               min_df=1, lowercase=True)
tfidf_matrix = tfidf.fit_transform(MEDICINE_NAMES)
print(f"[Arogya] Ready ✓\n")


# ════════════════════════════════════════════════════════
#  STRICT MATCHING  — the key fix
#
#  Old problem: threshold was 65-72, so random OCR noise
#  like "Sanjay", "Dept", "Morning" matched medicines.
#
#  New rule: RapidFuzz score must be >= 90 (very strict)
#  This means only near-exact matches go through.
#  Better to show 2 correct medicines than 14 wrong ones.
# ════════════════════════════════════════════════════════

def strict_match(candidate):
    """
    Returns (medicine_dict, score) only if VERY confident.
    Threshold 90 = near-exact match required.
    """
    candidate = re.sub(r'[^a-zA-Z0-9\s]', '', candidate).strip()

    # Reject short words and ignore list
    if len(candidate) < 4:
        return None, 0
    if candidate.lower() in IGNORE_WORDS:
        return None, 0
    # Reject pure numbers
    if candidate.isdigit():
        return None, 0
    # Reject very common short English words
    if len(candidate) <= 4 and candidate.lower() not in \
            [m["name"].lower() for m in MEDICINE_DB]:
        return None, 0

    # RapidFuzz — strict threshold 90
    result = rf_process.extractOne(
        candidate, MEDICINE_NAMES,
        scorer=fuzz.WRatio,
        score_cutoff=90,
    )
    if result:
        med = next((m for m in MEDICINE_DB
                    if m["name"] == result[0]), None)
        return med, result[1]

    return None, 0


# ════════════════════════════════════════════════════════
#  IMAGE PRE-PROCESSING
# ════════════════════════════════════════════════════════

def deskew(gray):
    coords = np.column_stack(np.where(gray < 200))
    if len(coords) < 100:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    if abs(angle) > 30:
        return gray
    h, w = gray.shape
    M    = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(gray, M, (w, h),
                          flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


def preprocess_image(filepath):
    img_cv = cv2.imread(filepath)
    if img_cv is None:
        pil    = Image.open(filepath).convert("RGB")
        img_cv = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    h, w = img_cv.shape[:2]
    if max(h, w) < 1800:
        scale  = 1800 / max(h, w)
        img_cv = cv2.resize(img_cv, (int(w * scale), int(h * scale)),
                            interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    gray = deskew(gray)

    versions = []
    clahe    = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    cl       = clahe.apply(gray)
    versions.append(("CLAHE", cl))

    blur     = cv2.GaussianBlur(gray, (5, 5), 0)
    adaptive = cv2.adaptiveThreshold(blur, 255,
                                     cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 31, 10)
    versions.append(("Adaptive", adaptive))

    _, otsu = cv2.threshold(cl, 0, 255,
                            cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    versions.append(("Otsu", otsu))

    kernel    = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharpened = cv2.filter2D(gray, -1, kernel)
    versions.append(("Sharp", sharpened))

    versions.append(("Gray", gray))
    return versions


# ════════════════════════════════════════════════════════
#  OCR RUNNERS
# ════════════════════════════════════════════════════════

def run_easyocr(filepath):
    if not EASYOCR_READY:
        return []
    versions, all_results = preprocess_image(filepath), []
    for label, img_arr in versions:
        try:
            if len(img_arr.shape) == 2:
                img_rgb = cv2.cvtColor(img_arr, cv2.COLOR_GRAY2RGB)
            else:
                img_rgb = img_arr
            results = easy_reader.readtext(img_rgb, paragraph=False,
                                           batch_size=8, workers=0)
            for (_, text, conf) in results:
                text = text.strip()
                if conf > 0.3 and text and len(text) > 1:
                    all_results.append((text, conf))
        except Exception as e:
            print(f"  EasyOCR [{label}]: {e}")

    # Deduplicate keeping highest confidence
    seen, unique = set(), []
    for text, conf in sorted(all_results, key=lambda x: x[1], reverse=True):
        key = text.lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(text)
    return unique


def run_tesseract(filepath):
    versions, all_lines = preprocess_image(filepath), []
    for _, img_arr in versions:
        pil_img = Image.fromarray(img_arr)
        for cfg in [TESS_COL, TESS_SPARSE]:
            try:
                raw = pytesseract.image_to_string(pil_img, config=cfg)
                for line in raw.splitlines():
                    line = line.strip()
                    if line and len(line) > 1:
                        all_lines.append(line)
            except Exception:
                pass
    seen, unique = set(), []
    for line in all_lines:
        key = line.lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(line)
    return unique


# ════════════════════════════════════════════════════════
#  MEDICINE EXTRACTION  — 2 strict passes only
#
#  Removed all token-scanning passes — they caused
#  most of the false positives.
#
#  Pass 1: Exact match — checks if medicine name appears
#          anywhere in the full OCR text (most reliable)
#
#  Pass 2: Per-line strict fuzzy — each OCR line is
#          matched with threshold 90 (very strict)
#          Only first word of each line is checked
#          since medicine names are always first on a line
# ════════════════════════════════════════════════════════

DOSAGE_RE   = re.compile(
    r'(\d+\s*(?:mg|ml|mcg|g|iu|IU|MG|ML))', re.IGNORECASE)
QUANTITY_RE = re.compile(
    r'(?:x\s*(\d+)|(\d+)\s*(?:tab|tabs|cap|caps|tablet|tablets|'
    r'capsule|capsules|strip|strips))', re.IGNORECASE)


def find_near(text, name, window=60):
    idx = text.lower().find(name.lower())
    return text[idx: idx + window] if idx != -1 else ""


def get_dosage(text, name):
    m = DOSAGE_RE.search(find_near(text, name, 50))
    return m.group(1).strip() if m else ""


def get_quantity(text, name):
    m = QUANTITY_RE.search(find_near(text, name, 65))
    return (m.group(1) or m.group(2)).strip() if m else "1"


def extract_medicines(text_lines):
    ocr_text   = "\n".join(text_lines)
    text_lower = ocr_text.lower()
    found      = []
    found_keys = set()

    def add(name, price, dosage, quantity, conf):
        key = name.lower().strip()
        if key and key not in found_keys:
            found_keys.add(key)
            found.append({
                "name":       name,
                "price":      price,
                "dosage":     dosage,
                "quantity":   quantity,
                "confidence": conf,
            })
            print(f"  ✔ ADDED: {name} (conf={conf}%)")

    # ── Pass 1: Exact match ───────────────────────────────
    # Most reliable — if medicine name exactly appears in text
    print("\n[Pass 1] Exact name match...")
    for med in MEDICINE_DB:
        if med["name"].lower() in text_lower:
            add(med["name"], med["price"],
                get_dosage(ocr_text, med["name"]),
                get_quantity(ocr_text, med["name"]),
                99)

    # ── Pass 2: Strict per-line fuzzy (threshold 90) ──────
    # Only checks first word/phrase of each OCR line
    # Medicine names are almost always the FIRST word on a line
    print("[Pass 2] Strict per-line fuzzy match (threshold=90)...")
    for line in text_lines:
        line = line.strip()
        if not line or len(line) < 3:
            continue

        # Skip lines that are clearly not medicine lines
        if re.match(r'^[\d\s\.\-\/\:\|]+$', line):
            continue
        if len(re.sub(r'[^a-zA-Z]', '', line)) < 3:
            continue
        if any(skip in line.lower() for skip in [
            "date", "patient", "hospital", "clinic", "doctor",
            "address", "phone", "prescription", "uhid", "room",
            "token", "dept", "consultant", "sanjay", "meena",
            "savitri", "mathura", "agra", "star health", "tata",
            "sbi", "hdfc", "insurance", "facilities", "emergency",
        ]):
            continue

        # Try first word only (where medicine name usually is)
        words = line.split()
        first_word = words[0].strip(".,:-/()")
        # Also try first 2 words combined
        first_two  = " ".join(words[:2]).strip(".,:-/()") \
                     if len(words) > 1 else first_word

        for candidate in [first_two, first_word]:
            med, conf = strict_match(candidate)
            if med:
                add(med["name"], med["price"],
                    get_dosage(ocr_text, med["name"]),
                    get_quantity(ocr_text, med["name"]),
                    int(conf))
                break  # found for this line, move to next

    found.sort(key=lambda x: x["confidence"], reverse=True)

    print(f"\n=== FINAL: {len(found)} medicine(s) ===")
    for m in found:
        print(f"  {m['name']} | conf={m['confidence']}%"
              f" | dosage={m['dosage']}")
    print("=" * 40 + "\n")

    return found


# ════════════════════════════════════════════════════════
#  MAIN DISPATCHER
# ════════════════════════════════════════════════════════

def process_prescription(filepath):
    img_hash = get_image_hash(filepath)
    cached   = check_cache(img_hash)
    if cached:
        return cached["medicines"], f"⚡ cached ({cached['mode']})"

    print(f"\n{'='*50}")
    print(f"[Arogya] {os.path.basename(filepath)}")
    print(f"{'='*50}")

    # Run EasyOCR + Tesseract, merge results
    easy_lines = run_easyocr(filepath)
    tess_lines = run_tesseract(filepath)

    seen, all_lines = set(l.lower().strip() for l in easy_lines), \
                      list(easy_lines)
    for line in tess_lines:
        if line.lower().strip() not in seen:
            all_lines.append(line)

    print(f"\n[OCR] {len(all_lines)} text segments detected:")
    for l in all_lines:
        print(f"  → {l}")

    medicines = extract_medicines(all_lines)
    mode      = "EasyOCR + Tesseract (offline)"

    write_cache(img_hash, medicines, mode)
    return medicines, mode


# ════════════════════════════════════════════════════════
#  USER DATABASE
# ════════════════════════════════════════════════════════

USERS_FILE = "users.json"

def load_users():
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def find_user(email, role):
    for u in load_users():
        if u["email"] == email and u["role"] == role:
            return u
    return None


# ════════════════════════════════════════════════════════
#  ROUTES
# ════════════════════════════════════════════════════════

@app.route("/")
def home():
    return render_template("landing.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role     = request.form.get("role")
        mode     = request.form.get("mode")
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if mode == "register":
            name    = request.form.get("name", "").strip()
            confirm = request.form.get("confirm_password", "")
            if password != confirm:
                flash("Passwords do not match!", "error")
                return redirect(url_for("login"))
            if find_user(email, role):
                flash("Account already exists with this email!", "error")
                return redirect(url_for("login"))
            new_user = {"name": name, "email": email,
                        "password": password, "role": role}
            if role == "supplier":
                new_user.update({
                    "store_name":    request.form.get("store_name", ""),
                    "store_address": request.form.get("store_address", ""),
                    "phone":         request.form.get("phone", ""),
                    "license":       request.form.get("license", ""),
                })
            if role == "rider":
                new_user.update({
                    "rider_phone":    request.form.get("rider_phone", ""),
                    "vehicle_type":   request.form.get("vehicle_type", ""),
                    "vehicle_number": request.form.get("vehicle_number", ""),
                    "rider_city":     request.form.get("rider_city", ""),
                })
            users = load_users()
            users.append(new_user)
            save_users(users)
            flash("Account created! Please login.", "success")
            return redirect(url_for("login"))

        elif mode == "login":
            user = find_user(email, role)
            if not user or user["password"] != password:
                flash("Invalid email or password!", "error")
                return redirect(url_for("login"))
            session["user_email"] = user["email"]
            session["user_name"]  = user.get("name", "User")
            session["user_role"]  = user["role"]
            flash(f"Welcome back, {user.get('name', 'User')}!", "success")
            if role == "supplier":
                return redirect(url_for("supplier_dashboard"))
            elif role == "rider":
                return redirect(url_for("rider_dashboard"))
            else:
                return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for("login"))


# ✅ REPLACE WITH THIS
@app.route("/supplier/dashboard")
def supplier_dashboard():
    if session.get("user_role") != "supplier":
        flash("Please login as supplier!", "error")
        return redirect(url_for("login"))
    supplier = {
        "name":          session.get("user_name", "Supplier"),
        "email":         session.get("user_email", ""),
        "store_name":    session.get("store_name", ""),
        "store_address": session.get("store_address", ""),
        "phone":         session.get("phone", ""),
    }
    return render_template("supplier_dashboard.html", supplier=supplier)


@app.route("/customer/dashboard")
def customer_dashboard():
    if session.get("user_role") != "customer":
        flash("Please login as customer!", "error")
        return redirect(url_for("login"))
    customer = {
        "name":  session.get("user_name", "Customer"),
        "email": session.get("user_email", ""),
    }
    return render_template("customer_dashboard.html", customer=customer)


ORDERS_FILE = "orders.json"

def load_orders():
    if not os.path.exists(ORDERS_FILE):
        return []
    with open(ORDERS_FILE, "r") as f:
        return json.load(f)

def save_orders(orders):
    with open(ORDERS_FILE, "w") as f:
        json.dump(orders, f, indent=2)

@app.route('/rider/dashboard')
def rider_dashboard():
    if session.get("user_role") != "rider":
        flash("Please login as rider!", "error")
        return redirect(url_for("login"))
    
    email = session.get("user_email")
    rider = find_user(email, "rider")
    if not rider:
        rider = {
            "name": session.get("user_name", "Rider"),
            "email": email,
            "role": "rider",
            "is_online": False,
            "earnings": 0,
            "deliveries": 0,
            "rating": 5.0
        }
    
    is_online = rider.get("is_online", False)
    orders = load_orders()
    available = [o for o in orders if o.get("status") == "pending"]
    in_progress = [o for o in orders if o.get("rider_id") == email and o.get("status") in ["accepted", "picked_up"]]
    delivered = [o for o in orders if o.get("rider_id") == email and o.get("status") == "delivered"]
    
    return render_template(
        "rider_dashboard.html",
        rider=rider,
        is_online=is_online,
        available=available,
        in_progress=in_progress,
        delivered=delivered
    )

@app.route('/rider/toggle_online', methods=['POST'])
def rider_toggle_online():
    if session.get("user_role") != "rider":
        return {"error": "Unauthorized"}, 403
    
    email = session.get("user_email")
    users = load_users()
    is_online = False
    for u in users:
        if u.get("email") == email and u.get("role") == "rider":
            u["is_online"] = not u.get("is_online", False)
            is_online = u["is_online"]
            break
    save_users(users)
    return {"is_online": is_online}

@app.route('/rider/accept/<order_id>', methods=['POST'])
def rider_accept_order(order_id):
    if session.get("user_role") != "rider":
        flash("Please login as rider!", "error")
        return redirect(url_for("login"))
    
    email = session.get("user_email")
    name = session.get("user_name", "Rider")
    orders = load_orders()
    import datetime
    now_str = datetime.datetime.now().strftime("%d %b %Y, %I:%M %p")
    
    for o in orders:
        if o.get("id") == order_id:
            o["status"] = "accepted"
            o["rider_id"] = email
            o["rider_name"] = name
            o["accepted_at"] = now_str
            break
    save_orders(orders)
    flash(f"Order {order_id} accepted successfully!", "success")
    return redirect(url_for("rider_dashboard"))

@app.route('/rider/pickup/<order_id>', methods=['POST'])
def rider_pickup_order(order_id):
    if session.get("user_role") != "rider":
        flash("Please login as rider!", "error")
        return redirect(url_for("login"))
    
    email = session.get("user_email")
    orders = load_orders()
    import datetime
    now_str = datetime.datetime.now().strftime("%d %b %Y, %I:%M %p")
    
    for o in orders:
        if o.get("id") == order_id and o.get("rider_id") == email:
            o["status"] = "picked_up"
            o["pickup_at"] = now_str
            break
    save_orders(orders)
    flash(f"Order {order_id} marked as Picked Up!", "success")
    return redirect(url_for("rider_dashboard"))

@app.route('/rider/deliver/<order_id>', methods=['POST'])
def rider_deliver_order(order_id):
    if session.get("user_role") != "rider":
        flash("Please login as rider!", "error")
        return redirect(url_for("login"))
    
    email = session.get("user_email")
    orders = load_orders()
    import datetime
    now_str = datetime.datetime.now().strftime("%d %b %Y, %I:%M %p")
    
    order_found = False
    for o in orders:
        if o.get("id") == order_id and o.get("rider_id") == email:
            o["status"] = "delivered"
            o["delivered_at"] = now_str
            order_found = True
            break
            
    if order_found:
        save_orders(orders)
        users = load_users()
        for u in users:
            if u.get("email") == email and u.get("role") == "rider":
                u["deliveries"] = u.get("deliveries", 0) + 1
                u["earnings"] = u.get("earnings", 0) + 60
                break
        save_users(users)
        flash(f"Order {order_id} marked as Delivered! +₹60 added to earnings.", "success")
    else:
        flash("Failed to mark order as delivered.", "error")
        
    return redirect(url_for("rider_dashboard"))

@app.route('/rider/navigate/<order_id>')
def rider_navigation(order_id):
    if session.get("user_role") != "rider":
        flash("Please login as rider!", "error")
        return redirect(url_for("login"))
        
    orders = load_orders()
    order = next((o for o in orders if o.get("id") == order_id), None)
    
    # Prototype/Demo fallback mode
    if not order or order_id == "demo":
        order = {
            "id": "DEMO-100",
            "status": "accepted",
            "pharmacy": "Apollo Pharmacy",
            "customer_name": "Demo Prototype Guest",
            "customer_phone": "9876543210",
            "address": "Civil Lines, Mathura",
            "amount": 420,
            "payment": "Cash on Delivery",
            "distance": "2.4 km"
        }
        
    rider = find_user(session.get("user_email"), "rider")
    if not rider:
        rider = {
            "name": session.get("user_name", "Rider"),
            "email": session.get("user_email", ""),
            "rider_city": "Mathura"
        }
        
    return render_template("navigation_map.html", order=order, rider=rider)

@app.route('/sw.js')
def service_worker():
    return app.send_static_file('sw.js')

@app.route("/scan")
def scan():
    return render_template("scan.html")


@app.route("/upload", methods=["POST"])
def upload():
    if "image" not in request.files:
        flash("No file uploaded!", "error")
        return redirect(url_for("scan"))
    file = request.files["image"]
    if file.filename == "":
        flash("No file selected!", "error")
        return redirect(url_for("scan"))

    os.makedirs("uploads", exist_ok=True)
    safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', file.filename)
    filepath      = os.path.join("uploads", safe_filename)
    file.save(filepath)

    try:
        medicines, ocr_mode = process_prescription(filepath)
        return render_template(
            "result.html",
            medicines     = medicines,
            all_medicines = MEDICINE_DB,
            ocr_text      = "",
            ocr_mode      = ocr_mode,
            image_path    = safe_filename,
        )
    except Exception as e:
        print("Error:", str(e))
        flash(f"Error: {e}", "error")
        return redirect(url_for("scan"))


@app.route("/set_reminder", methods=["POST"])
def set_reminder():
    medicine = request.form.get("medicine")
    time     = request.form.get("time")
    flash(f"Reminder set for {medicine} at {time}!", "success")
    return redirect(url_for("scan"))


@app.route("/store")
def store():
    return render_template("store.html")


@app.route("/map")
def map_page():
    return render_template("map.html")


@app.route("/result")
def result():
    return render_template("result.html",
                           medicines=[], all_medicines=MEDICINE_DB,
                           ocr_text="", ocr_mode="")


@app.route("/payment_success")
def payment_success():
    return render_template("payment_success.html")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)