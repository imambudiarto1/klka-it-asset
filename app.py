import csv
import datetime
import io
import os
from functools import wraps

from flask import (Flask, redirect, render_template, request,
                   session, url_for, flash, abort, Response)
from werkzeug.security import generate_password_hash, check_password_hash

import database as db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "klka-asset-secret-2026")

CATEGORIES = ["Laptop", "Desktop", "Monitor", "Printer", "UPS", "Switch",
              "Router", "Server", "Telephone", "Scanner", "Projector", "Other"]
STATUSES   = ["Active", "In Repair", "Retired", "Lost", "In Storage"]
DEPARTMENTS = [
    "Finance, Account and Tender", "Infrastructure & Utility", "IT",
    "Procurement", "Corporate Communication", "Legal", "Human Resource",
    "Production", "Tax", "Marketing", "Office Administration",
    "Sustainability", "Procurement (Insurance)",
]

db.init_db()


# ── Seed admin default ────────────────────────────────────────────────────────
def _seed():
    if db.count_users() == 0:
        db.create_user({
            "name": "Administrator",
            "email": "admin@klk.co.id",
            "password_hash": generate_password_hash("klka2026"),
            "role": "admin",
            "created_at": datetime.datetime.now().isoformat(),
        })
_seed()


# ── Auth helpers ──────────────────────────────────────────────────────────────
def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return db.get_user_by_email(session.get("user_email", ""))


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


# ── Login / Logout ────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw    = request.form.get("password", "")
        user  = db.get_user_by_email(email)
        if not user or not check_password_hash(user["password_hash"], pw):
            flash("Email atau password salah.", "danger")
            return redirect(url_for("login"))
        session["user_id"]    = user["id"]
        session["user_email"] = user["email"]
        session["user_name"]  = user["name"]
        session["user_role"]  = user["role"]
        return redirect(request.args.get("next") or url_for("index"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    assets   = db.get_all_assets()
    expiring = db.get_warranty_expiring(30)
    stats = {
        "total":    len(assets),
        "active":   sum(1 for a in assets if a["status"] == "Active"),
        "repair":   sum(1 for a in assets if a["status"] == "In Repair"),
        "retired":  sum(1 for a in assets if a["status"] == "Retired"),
        "storage":  sum(1 for a in assets if a["status"] == "In Storage"),
        "lost":     sum(1 for a in assets if a["status"] == "Lost"),
    }
    by_category = {}
    for a in assets:
        by_category[a["category"]] = by_category.get(a["category"], 0) + 1
    return render_template("index.html", stats=stats,
                           by_category=by_category, expiring=expiring)


# ── Asset List ────────────────────────────────────────────────────────────────
@app.route("/assets")
@login_required
def asset_list():
    search     = request.args.get("q", "")
    f_category = request.args.get("category", "")
    f_status   = request.args.get("status", "")
    f_dept     = request.args.get("department", "")
    assets = db.get_all_assets(search, f_category, f_status, f_dept)
    return render_template("assets.html", assets=assets,
                           categories=CATEGORIES, statuses=STATUSES,
                           departments=DEPARTMENTS,
                           search=search, f_category=f_category,
                           f_status=f_status, f_dept=f_dept)


# ── Add Asset ─────────────────────────────────────────────────────────────────
@app.route("/assets/add", methods=["GET", "POST"])
@login_required
def asset_add():
    if request.method == "POST":
        now = datetime.datetime.now().isoformat()
        tag = request.form.get("asset_tag", "").strip() or db.get_next_asset_tag()
        aid = db.create_asset({
            "asset_tag":       tag,
            "asset_name":      request.form.get("asset_name", "").strip(),
            "category":        request.form.get("category", ""),
            "brand":           request.form.get("brand", "").strip(),
            "model":           request.form.get("model", "").strip(),
            "serial_number":   request.form.get("serial_number", "").strip(),
            "status":          request.form.get("status", "Active"),
            "location":        request.form.get("location", "").strip(),
            "department":      request.form.get("department", ""),
            "assigned_to":     request.form.get("assigned_to", "").strip(),
            "assigned_email":  request.form.get("assigned_email", "").strip(),
            "purchase_date":   request.form.get("purchase_date", ""),
            "warranty_expiry": request.form.get("warranty_expiry", ""),
            "notes":           request.form.get("notes", "").strip(),
            "created_at":      now,
            "updated_at":      now,
        })
        db.add_history(aid, "Tambah", f"Asset {tag} ditambahkan", session["user_name"])
        flash(f"Asset {tag} berhasil ditambahkan.", "success")
        return redirect(url_for("asset_list"))
    tag = db.get_next_asset_tag()
    return render_template("asset_form.html", asset=None, tag=tag,
                           categories=CATEGORIES, statuses=STATUSES,
                           departments=DEPARTMENTS)


# ── Edit Asset ────────────────────────────────────────────────────────────────
@app.route("/assets/<int:aid>/edit", methods=["GET", "POST"])
@login_required
def asset_edit(aid):
    asset = db.get_asset_by_id(aid)
    if not asset:
        abort(404)
    if request.method == "POST":
        db.update_asset(aid, {
            "asset_tag":       request.form.get("asset_tag", "").strip(),
            "asset_name":      request.form.get("asset_name", "").strip(),
            "category":        request.form.get("category", ""),
            "brand":           request.form.get("brand", "").strip(),
            "model":           request.form.get("model", "").strip(),
            "serial_number":   request.form.get("serial_number", "").strip(),
            "status":          request.form.get("status", "Active"),
            "location":        request.form.get("location", "").strip(),
            "department":      request.form.get("department", ""),
            "assigned_to":     request.form.get("assigned_to", "").strip(),
            "assigned_email":  request.form.get("assigned_email", "").strip(),
            "purchase_date":   request.form.get("purchase_date", ""),
            "warranty_expiry": request.form.get("warranty_expiry", ""),
            "notes":           request.form.get("notes", "").strip(),
            "updated_at":      datetime.datetime.now().isoformat(),
        })
        db.add_history(aid, "Edit", f"Data asset diperbarui", session["user_name"])
        flash("Asset berhasil diperbarui.", "success")
        return redirect(url_for("asset_list"))
    history = db.get_history(aid)
    return render_template("asset_form.html", asset=asset, tag=asset["asset_tag"],
                           categories=CATEGORIES, statuses=STATUSES,
                           departments=DEPARTMENTS, history=history)


# ── Export Excel (CSV) ───────────────────────────────────────────────────────
@app.route("/assets/export")
@login_required
def asset_export():
    search     = request.args.get("q", "")
    f_category = request.args.get("category", "")
    f_status   = request.args.get("status", "")
    f_dept     = request.args.get("department", "")
    assets = db.get_all_assets(search, f_category, f_status, f_dept)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Asset Tag", "Nama Asset", "Kategori", "Brand", "Model",
        "Serial Number", "Status", "Lokasi", "Departemen",
        "Assigned To", "Assigned Email", "Tanggal Pembelian",
        "Garansi Sampai", "Catatan", "Dibuat"
    ])
    for a in assets:
        writer.writerow([
            a.get("asset_tag",""), a.get("asset_name",""), a.get("category",""),
            a.get("brand",""), a.get("model",""), a.get("serial_number",""),
            a.get("status",""), a.get("location",""), a.get("department",""),
            a.get("assigned_to",""), a.get("assigned_email",""),
            a.get("purchase_date",""), a.get("warranty_expiry",""),
            a.get("notes",""), a.get("created_at","")[:10] if a.get("created_at") else "",
        ])

    output.seek(0)
    fname = f"KLKA_IT_Asset_{datetime.date.today().isoformat()}.csv"
    return Response(
        "﻿" + output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={fname}"}
    )


# ── Delete Asset ──────────────────────────────────────────────────────────────
@app.route("/assets/<int:aid>/delete", methods=["POST"])
@login_required
def asset_delete(aid):
    asset = db.get_asset_by_id(aid)
    if asset:
        db.delete_asset(aid)
        flash(f"Asset {asset['asset_tag']} berhasil dihapus.", "success")
    return redirect(url_for("asset_list"))


# ── User Management ───────────────────────────────────────────────────────────
@app.route("/users")
@login_required
def user_list():
    if session.get("user_role") != "admin":
        abort(403)
    users = db.get_all_users()
    return render_template("users.html", users=users)


@app.route("/users/add", methods=["POST"])
@login_required
def user_add():
    if session.get("user_role") != "admin":
        abort(403)
    email = request.form.get("email", "").strip().lower()
    if db.get_user_by_email(email):
        flash("Email sudah terdaftar.", "danger")
        return redirect(url_for("user_list"))
    db.create_user({
        "name":          request.form.get("name", "").strip(),
        "email":         email,
        "password_hash": generate_password_hash(request.form.get("password", "klka2026")),
        "role":          request.form.get("role", "staff"),
        "created_at":    datetime.datetime.now().isoformat(),
    })
    flash("User berhasil ditambahkan.", "success")
    return redirect(url_for("user_list"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
