"""3D Print Cost Calculator: a small Flask app with an anonymous-first UI."""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "data" / "calculator.db"))

DEFAULT_MATERIALS = {
    "PLA": {"cost": 0.05, "density": 1.24, "unit": "g", "color": "#7559e8"},
    "PETG": {"cost": 0.06, "density": 1.27, "unit": "g", "color": "#159a9c"},
    "ABS": {"cost": 0.08, "density": 1.04, "unit": "g", "color": "#ec8a3d"},
    "ASA": {"cost": 0.09, "density": 1.07, "unit": "g", "color": "#e35c7a"},
    "TPU": {"cost": 0.07, "density": 1.21, "unit": "g", "color": "#e4b84a"},
    "Resin": {"cost": 0.10, "density": 1.10, "unit": "g", "color": "#3c8cda"},
}
CURRENCIES = {"USD": "$", "EUR": "€", "GBP": "£", "CAD": "CA$", "AUD": "A$"}

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    MAX_CONTENT_LENGTH=64 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true",
)


def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS preferences (
                owner_sub TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS material_presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT, owner_sub TEXT NOT NULL, name TEXT NOT NULL,
                data TEXT NOT NULL, created_at INTEGER NOT NULL,
                UNIQUE(owner_sub, name)
            );
            CREATE TABLE IF NOT EXISTS printer_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT, owner_sub TEXT NOT NULL, name TEXT NOT NULL,
                data TEXT NOT NULL, created_at INTEGER NOT NULL,
                UNIQUE(owner_sub, name)
            );
            CREATE TABLE IF NOT EXISTS quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT, owner_sub TEXT NOT NULL, name TEXT NOT NULL,
                data TEXT NOT NULL, created_at INTEGER NOT NULL
            );
            """
        )


with app.app_context():
    init_db()


def number(value, default=0.0, minimum=0.0, maximum=1_000_000_000.0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def calculate(payload: dict) -> dict:
    """Calculate a quote in cents-friendly floats; all inputs are bounded at the API edge."""
    quantity = int(number(payload.get("quantity"), 1, 1, 100_000))
    hours = number(payload.get("print_hours"), 0, 0, 100_000) + number(payload.get("print_minutes"), 0, 0, 59) / 60
    labor_hours = number(payload.get("labor_hours"), 0, 0, 100_000) + number(payload.get("labor_minutes"), 0, 0, 59) / 60
    setup_hours = number(payload.get("setup_minutes"), 0, 0, 100_000) / 60
    material = 0.0
    weight = 0.0
    volume = 0.0
    lines = []
    for raw in payload.get("material_lines", [])[:20]:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "Custom")[:60]
        grams = number(raw.get("grams"), 0, 0, 100_000)
        ml = number(raw.get("volume_ml"), 0, 0, 100_000)
        density = number(raw.get("density"), 1.1, 0.01, 20)
        if grams <= 0 and ml > 0:
            grams = ml * density
        cost = number(raw.get("cost_per_gram"), 0, 0, 10_000)
        line_cost = grams * cost
        material += line_cost
        weight += grams
        volume += ml or grams / density
        lines.append({"name": name, "grams": round(grams, 3), "cost": round(line_cost, 2)})
    waste_rate = number(payload.get("waste_rate"), 10, 0, 100) / 100
    failure_rate = number(payload.get("failure_rate"), 5, 0, 100) / 100
    # Form values describe one part; batch quantity scales repeatable costs. Setup is once.
    material_with_waste = material * (1 + waste_rate) * quantity
    labor_rate = number(payload.get("labor_rate"), 20, 0, 100_000)
    labor_per_unit = labor_hours * labor_rate
    labor = labor_per_unit * quantity + setup_hours * labor_rate
    total_machine_hours = hours * quantity
    electricity_per_unit = hours * number(payload.get("power_watts"), 120, 0, 10_000) / 1000 * number(payload.get("electricity_rate"), 0.16, 0, 100)
    electricity = electricity_per_unit * quantity
    depreciation_per_unit = hours * number(payload.get("printer_cost"), 800, 0, 10_000_000) / number(payload.get("printer_life_hours"), 3000, 1, 10_000_000)
    depreciation = depreciation_per_unit * quantity
    maintenance_per_unit = hours * number(payload.get("maintenance_rate"), 0.05, 0, 100_000)
    maintenance = maintenance_per_unit * quantity
    hardware = number(payload.get("hardware"), 0, 0, 10_000_000) * quantity
    packaging = number(payload.get("packaging"), 0, 0, 10_000_000) * quantity
    overhead = number(payload.get("overhead_rate"), 0, 0, 100) / 100
    setup = number(payload.get("setup_cost"), 0, 0, 10_000_000)
    failure_reserve = (material_with_waste + labor + electricity + depreciation + maintenance) * failure_rate
    direct = material_with_waste + labor + electricity + depreciation + maintenance + failure_reserve + hardware + packaging + setup
    overhead_cost = direct * overhead
    before_tax = direct + overhead_cost
    tax = before_tax * number(payload.get("tax_rate"), 0, 0, 100) / 100
    total = before_tax + tax
    unit = total / quantity
    result = {
        "quantity": quantity, "hours": round(hours, 3), "weight": round(weight * quantity, 3), "unit_weight": round(weight, 3), "volume": round(volume * quantity, 3),
        "total": round(total + 1e-9, 2), "unit_cost": round(unit + 1e-9, 2),
        "tax": round(tax + 1e-9, 2), "before_tax": round(before_tax + 1e-9, 2),
        "breakdown": {
            "Material": round(material_with_waste + 1e-9, 2), "Labor": round(labor + 1e-9, 2),
            "Electricity": round(electricity + 1e-9, 2), "Depreciation": round(depreciation + 1e-9, 2),
            "Maintenance": round(maintenance + 1e-9, 2), "Failure reserve": round(failure_reserve + 1e-9, 2),
            "Hardware": round(hardware + 1e-9, 2), "Packaging": round(packaging + 1e-9, 2),
            "Setup": round(setup + 1e-9, 2), "Overhead": round(overhead_cost + 1e-9, 2), "Tax": round(tax + 1e-9, 2),
        },
        "lines": lines,
        "prices": {str(m): round(unit / (1 - m / 100) + 1e-9, 2) for m in (25, 40, 60, 80)},
    }
    custom_margin = number(payload.get("custom_margin"), 50, 0, 99.9)
    result["prices"]["custom"] = round(unit / (1 - custom_margin / 100) + 1e-9, 2)
    return result


def owner():
    return session.get("oidc_sub")


def require_owner():
    if not owner():
        return jsonify({"error": "Sign in is required to save data."}), 401
    return None


def oidc_configured():
    return all(os.environ.get(key) for key in ("OIDC_ISSUER_URL", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "OIDC_REDIRECT_URI", "SECRET_KEY"))


def oidc_metadata():
    issuer = os.environ["OIDC_ISSUER_URL"].rstrip("/")
    request_ = Request(issuer + "/.well-known/openid-configuration", headers={"Accept": "application/json"})
    with urlopen(request_, timeout=5) as response:
        return json.load(response)


@app.get("/")
def index():
    return render_template("index.html", materials=DEFAULT_MATERIALS, currencies=CURRENCIES, logged_in=bool(owner()), login_enabled=oidc_configured(), user=session.get("oidc_name"))


@app.get("/healthz")
def healthz():
    try:
        with db() as conn:
            conn.execute("SELECT 1")
        return jsonify({"status": "ok"})
    except sqlite3.Error:
        return jsonify({"status": "error"}), 503


@app.post("/api/calculate")
def api_calculate():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON object required."}), 400
    return jsonify(calculate(payload))


@app.get("/login")
def login():
    if not oidc_configured():
        return render_template("login_disabled.html"), 503
    metadata = oidc_metadata()
    state = secrets.token_urlsafe(24)
    session["oidc_state"] = state
    return redirect(metadata["authorization_endpoint"] + "?" + urlencode({
        "client_id": os.environ["OIDC_CLIENT_ID"], "response_type": "code", "scope": "openid profile email",
        "redirect_uri": os.environ["OIDC_REDIRECT_URI"], "state": state,
    }))


@app.get("/auth/callback")
def auth_callback():
    if not oidc_configured() or request.args.get("state") != session.pop("oidc_state", None):
        return "Invalid or expired sign-in request.", 400
    metadata = oidc_metadata()
    body = urlencode({
        "grant_type": "authorization_code",
        "code": request.args.get("code", ""),
        "redirect_uri": os.environ["OIDC_REDIRECT_URI"],
        "client_id": os.environ["OIDC_CLIENT_ID"],
        "client_secret": os.environ["OIDC_CLIENT_SECRET"],
    }).encode()
    token_request = Request(metadata["token_endpoint"], data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urlopen(token_request, timeout=5) as response:
        token = json.load(response)
    user_request = Request(metadata["userinfo_endpoint"], headers={"Authorization": "Bearer " + token["access_token"]})
    with urlopen(user_request, timeout=5) as response:
        profile = json.load(response)
    if not profile.get("sub"):
        return "Identity provider returned no subject.", 400
    session.clear()
    session.update(oidc_sub=profile["sub"], oidc_name=profile.get("name") or profile.get("preferred_username") or profile.get("email") or "Signed in")
    return redirect(url_for("index"))


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/api/preferences", methods=["GET", "POST"])
def preferences_api():
    denied = require_owner()
    if denied: return denied
    sub = owner()
    if request.method == "POST":
        data = request.get_json(silent=True)
        if not isinstance(data, dict): return jsonify({"error": "JSON object required."}), 400
        with db() as conn:
            conn.execute("INSERT INTO preferences(owner_sub,data,updated_at) VALUES(?,?,?) ON CONFLICT(owner_sub) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at", (sub, json.dumps(data), int(time.time())))
    with db() as conn:
        row = conn.execute("SELECT data FROM preferences WHERE owner_sub=?", (sub,)).fetchone()
    return jsonify(json.loads(row["data"]) if row else {})


def collection_api(table, name):
    denied = require_owner()
    if denied: return denied
    sub = owner()
    if request.method == "POST":
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not str(data.get("name") or "").strip(): return jsonify({"error": "A name is required."}), 400
        with db() as conn:
            conn.execute(f"INSERT INTO {table}(owner_sub,name,data,created_at) VALUES(?,?,?,?) ON CONFLICT(owner_sub,name) DO UPDATE SET data=excluded.data", (sub, str(data["name"])[:100], json.dumps(data), int(time.time())))
    with db() as conn:
        rows = conn.execute(f"SELECT id,name,data,created_at FROM {table} WHERE owner_sub=? ORDER BY created_at DESC", (sub,)).fetchall()
    return jsonify([{"id": r["id"], "name": r["name"], "data": json.loads(r["data"]), "created_at": r["created_at"]} for r in rows])


@app.route("/api/material-presets", methods=["GET", "POST"])
def material_presets(): return collection_api("material_presets", "material preset")


@app.route("/api/printer-profiles", methods=["GET", "POST"])
def printer_profiles(): return collection_api("printer_profiles", "printer profile")


@app.route("/api/quotes", methods=["GET", "POST"])
def quotes(): return collection_api("quotes", "quote")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
