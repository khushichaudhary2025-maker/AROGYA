from flask import Flask, render_template, request, redirect, url_for, session, flash
import json, os, re
from PIL import Image
import pytesseract

app = Flask(__name__)
app.secret_key = "arogya_secret_key_2025"

# ── TESSERACT PATH (Windows) ──
# Make sure Tesseract is installed from:
# https://github.com/UB-Mannheim/tesseract/wiki
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# ── MEDICINE DATABASE ──
# These are common medicines Tesseract will try to match against
MEDICINE_DB = [
    {"name": "Paracetamol",      "price": 12},
    {"name": "Dolo 650",         "price": 22},
    {"name": "Azithromycin",     "price": 85},
    {"name": "Amoxicillin",      "price": 72},
    {"name": "Cetrizine",        "price": 18},
    {"name": "Metformin",        "price": 32},
    {"name": "Omeprazole",       "price": 45},
    {"name": "Pantoprazole",     "price": 38},
    {"name": "Ibuprofen",        "price": 25},
    {"name": "Aspirin",          "price": 15},
    {"name": "Atorvastatin",     "price": 55},
    {"name": "Amlodipine",       "price": 42},
    {"name": "Losartan",         "price": 48},
    {"name": "Metoprolol",       "price": 35},
    {"name": "Ciprofloxacin",    "price": 65},
    {"name": "Doxycycline",      "price": 58},
    {"name": "Cefixime",         "price": 88},
    {"name": "Levocetirizine",   "price": 28},
    {"name": "Montelukast",      "price": 75},
    {"name": "Salbutamol",       "price": 45},
    {"name": "Prednisolone",     "price": 32},
    {"name": "Diclofenac",       "price": 22},
    {"name": "Tramadol",         "price": 55},
    {"name": "Ranitidine",       "price": 18},
    {"name": "Domperidone",      "price": 28},
    {"name": "Ondansetron",      "price": 35},
    {"name": "Metronidazole",    "price": 20},
    {"name": "Albendazole",      "price": 15},
    {"name": "Vitamin C",        "price": 25},
    {"name": "Vitamin D3",       "price": 42},
    {"name": "Vitamin B12",      "price": 38},
    {"name": "Iron",             "price": 22},
    {"name": "Folic Acid",       "price": 18},
    {"name": "Calcium",          "price": 35},
    {"name": "Zinc",             "price": 28},
    {"name": "Insulin",          "price": 180},
    {"name": "Glimepiride",      "price": 45},
    {"name": "Sitagliptin",      "price": 95},
    {"name": "Thyronorm",        "price": 42},
    {"name": "Levothyroxine",    "price": 38},
    {"name": "Warfarin",         "price": 25},
    {"name": "Clopidogrel",      "price": 55},
    {"name": "Digoxin",          "price": 28},
    {"name": "Furosemide",       "price": 18},
    {"name": "Spironolactone",   "price": 35},
    {"name": "Hydroxychloroquine","price": 45},
    {"name": "Aceclofenac",      "price": 28},
    {"name": "Sertraline",       "price": 65},
    {"name": "Escitalopram",     "price": 55},
    {"name": "Alprazolam",       "price": 35},
    {"name": "Clonazepam",       "price": 28},
    {"name": "Gabapentin",       "price": 48},
    {"name": "Pregabalin",       "price": 75},
    {"name": "Pantop",           "price": 38},
    {"name": "Pan D",            "price": 45},
    {"name": "Crocin",           "price": 15},
    {"name": "Combiflam",        "price": 28},
    {"name": "Allegra",          "price": 55},
    {"name": "Zyrtec",           "price": 48},
    {"name": "Augmentin",        "price": 95},
    {"name": "Taxim",            "price": 88},
    {"name": "Azee",             "price": 75},
]


# ── EXTRACT MEDICINES FROM OCR TEXT ──
def extract_medicines(ocr_text):
    found = []
    # Clean the text
    text_lower = ocr_text.lower()
    text_lines = ocr_text.split('\n')

    # Method 1: Match against medicine database
    for med in MEDICINE_DB:
        if med["name"].lower() in text_lower:
            # Avoid duplicates
            if not any(f["name"] == med["name"] for f in found):
                found.append({
                    "name":     med["name"],
                    "price":    med["price"],
                    "dosage":   extract_dosage(ocr_text, med["name"]),
                    "quantity": extract_quantity(ocr_text, med["name"])
                })

    # Method 2: Find lines with dosage patterns (mg, ml, tablet, cap)
    dosage_pattern = re.compile(
        r'([A-Za-z][A-Za-z\s]+?)\s*(\d+\s*(?:mg|ml|mcg|g|iu|IU|MG|ML))',
        re.IGNORECASE
    )
    for match in dosage_pattern.finditer(ocr_text):
        med_name = match.group(1).strip()
        dosage   = match.group(2).strip()
        # Filter out very short or very long names
        if 3 < len(med_name) < 30:
            if not any(f["name"].lower() == med_name.lower() for f in found):
                found.append({
                    "name":     med_name.title(),
                    "price":    get_price(med_name),
                    "dosage":   dosage,
                    "quantity": extract_quantity(ocr_text, med_name)
                })

    # Method 3: Find lines with tablet/capsule/syrup keywords
    med_keywords = ['tablet', 'tab', 'cap', 'capsule', 'syrup', 'injection', 'drops', 'cream', 'ointment', 'gel']
    for line in text_lines:
        line = line.strip()
        if not line:
            continue
        line_lower = line.lower()
        if any(kw in line_lower for kw in med_keywords):
            # Extract medicine name from the line
            parts = line.split()
            if parts and len(parts[0]) > 2:
                med_name = parts[0].strip('.,:-')
                if not any(f["name"].lower() == med_name.lower() for f in found):
                    found.append({
                        "name":     med_name.title(),
                        "price":    get_price(med_name),
                        "dosage":   "",
                        "quantity": "1"
                    })

    return found


def extract_dosage(text, medicine_name):
    pattern = re.compile(
        re.escape(medicine_name) + r'\s*(\d+\s*(?:mg|ml|mcg|g|iu|IU|MG|ML))',
        re.IGNORECASE
    )
    match = pattern.search(text)
    if match:
        return match.group(1)
    # Generic dosage search near medicine name
    idx = text.lower().find(medicine_name.lower())
    if idx != -1:
        nearby = text[idx:idx+30]
        dm = re.search(r'(\d+\s*(?:mg|ml|mcg|g|iu))', nearby, re.IGNORECASE)
        if dm:
            return dm.group(1)
    return ""


def extract_quantity(text, medicine_name):
    idx = text.lower().find(medicine_name.lower())
    if idx != -1:
        nearby = text[idx:idx+50]
        qm = re.search(r'x\s*(\d+)|(\d+)\s*(?:tab|cap|tablet|capsule|strip|strips)', nearby, re.IGNORECASE)
        if qm:
            return qm.group(1) or qm.group(2)
    return "1"


def get_price(medicine_name):
    for med in MEDICINE_DB:
        if med["name"].lower() in medicine_name.lower():
            return med["price"]
    return 30  # default price


# ── USER DATABASE ──
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
    users = load_users()
    for u in users:
        if u["email"] == email and u["role"] == role:
            return u
    return None


# ── HOME ──
@app.route("/")
def home():
    return render_template("landing.html")


# ── LOGIN / REGISTER ──
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

            new_user = {
                "name":      name,
                "email":     email,
                "password":  password,
                "role":      role,
                "github_id": request.form.get("github_id", "")
            }

            if role == "supplier":
                new_user["store_name"]    = request.form.get("store_name", "")
                new_user["store_address"] = request.form.get("store_address", "")
                new_user["phone"]         = request.form.get("phone", "")
                new_user["license"]       = request.form.get("license", "")

            if role == "rider":
                new_user["rider_phone"]    = request.form.get("rider_phone", "")
                new_user["vehicle_type"]   = request.form.get("vehicle_type", "")
                new_user["vehicle_number"] = request.form.get("vehicle_number", "")
                new_user["rider_city"]     = request.form.get("rider_city", "")

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
            session["user_github_id"] = user.get("github_id", "")
            flash("Welcome back, " + user.get("name", "User") + "!", "success")

            if role == "supplier":
                return redirect(url_for("supplier_dashboard"))
            elif role == "rider":
                return redirect(url_for("rider_dashboard"))
            else:
                return redirect(url_for("home"))

    return render_template("login.html")


# ── LOGOUT ──
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for("login"))


# ── SUPPLIER DASHBOARD ──
@app.route("/supplier/dashboard")
def supplier_dashboard():
    if session.get("user_role") != "supplier":
        flash("Please login as supplier!", "error")
        return redirect(url_for("login"))
    return render_template("supplier_dashboard.html")


# ── RIDER DASHBOARD ──
@app.route("/rider/dashboard")
def rider_dashboard():
    if session.get("user_role") != "rider":
        flash("Please login as rider!", "error")
        return redirect(url_for("login"))
    return render_template("rider_dashboard.html")


# ── SCAN ──
@app.route("/scan")
def scan():
    return render_template("scan.html")


# ── UPLOAD + OCR ──
@app.route("/upload", methods=["POST"])
def upload():
    if "image" not in request.files:
        flash("No file uploaded!", "error")
        return redirect(url_for("scan"))

    file = request.files["image"]
    if file.filename == "":
        flash("No file selected!", "error")
        return redirect(url_for("scan"))

    # Save uploaded file
    os.makedirs("uploads", exist_ok=True)
    filepath = os.path.join("uploads", file.filename)
    file.save(filepath)

    try:
        # ── STEP 1: Open image with Pillow ──
        img = Image.open(filepath)

        # ── STEP 2: Convert to RGB if needed ──
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # ── STEP 3: Run Tesseract OCR ──
        # Custom config for better results on prescriptions
        custom_config = r'--oem 3 --psm 6'
        ocr_text = pytesseract.image_to_string(img, config=custom_config, lang='eng')

        print("=== OCR RAW TEXT ===")
        print(ocr_text)
        print("===================")

        # ── STEP 4: Extract medicines from OCR text ──
        detected_medicines = extract_medicines(ocr_text)

        print("=== DETECTED MEDICINES ===")
        print(detected_medicines)
        print("==========================")

        # ── STEP 5: Render result page ──
        return render_template(
            "result.html",
            medicines     = detected_medicines,
            all_medicines = MEDICINE_DB,
            ocr_text      = ocr_text,
            image_path    = file.filename
        )

    except Exception as e:
        print("OCR Error:", str(e))
        flash("OCR Error: " + str(e) + " — Make sure Tesseract is installed!", "error")
        return redirect(url_for("scan"))


# ── SET REMINDER ──
@app.route("/set_reminder", methods=["POST"])
def set_reminder():
    medicine = request.form.get("medicine")
    time     = request.form.get("time")
    flash("Reminder set for " + medicine + " at " + time + "!", "success")
    return redirect(url_for("scan"))


# ── STORE ──
@app.route("/store")
def store():
    return render_template("store.html")


# ── MAP ──
@app.route("/map")
def map_page():
    return render_template("map.html")


# ── RESULT ──
@app.route("/result")
def result():
    return render_template("result.html", medicines=[], all_medicines=MEDICINE_DB, ocr_text="")


# ── PAYMENT SUCCESS ──
@app.route("/payment_success")
def payment_success():
    return render_template("payment_success.html")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)