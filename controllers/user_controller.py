from flask import Blueprint, request, jsonify
from db import get_connection
from datetime import datetime, date, time
import psycopg2.extras
import bcrypt

user_bp = Blueprint("user", __name__)

# -----------------------
# 🔐 Login
# -----------------------
@user_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    conn.close()

    if user and bcrypt.checkpw(password.encode(), user["password"].encode()):
        return jsonify({
            "success": True,
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"]
            }
        })
    return jsonify({"success": False, "message": "Invalid credentials"}), 401


# -----------------------
# 👤 Get Profile
# -----------------------
@user_bp.route("/profile/<int:user_id>", methods=["GET"])
def get_profile(user_id):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT id, name, email, phone, age, batch, role FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    conn.close()

    if user:
        return jsonify(user)
    return jsonify({"error": "User not found"}), 404


# -----------------------
# ✅ Attendance Log
# -----------------------
@user_bp.route("/attendance/<int:user_id>", methods=["GET"])
def get_attendance(user_id):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        SELECT date, check_in, check_out, late_minutes, early_minutes, is_present, is_paid_leave
        FROM attendance
        WHERE user_id = %s
        ORDER BY date DESC
    """, (user_id,))
    logs = cursor.fetchall()
    conn.close()

    return jsonify(logs)


# -----------------------
# 💰 Latest Salary
# -----------------------
@user_bp.route("/salary/<int:user_id>", methods=["GET"])
def get_salary(user_id):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("""
        SELECT * FROM salary
        WHERE user_id = %s
        ORDER BY year DESC, month DESC
        LIMIT 1
    """, (user_id,))
    salary = cursor.fetchone()
    conn.close()

    if salary:
        return jsonify(salary)
    return jsonify({"error": "No salary record found"}), 404


# -----------------------
# ⏱️ Check-In
# -----------------------
@user_bp.route("/check-in", methods=["POST"])
def check_in():
    data = request.get_json()
    user_id = data.get("user_id")
    now = datetime.now()
    today = now.date()
    check_in_time = now.time()

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM attendance WHERE user_id = %s AND date = %s", (user_id, today))
    if cursor.fetchone():
        conn.close()
        return jsonify({"message": "Already checked in"}), 400

    late_limit = time(9, 40)
    late_minutes = 0
    if check_in_time > late_limit:
        late_minutes = (datetime.combine(today, check_in_time) - datetime.combine(today, late_limit)).seconds // 60

    cursor.execute("""
        INSERT INTO attendance (user_id, date, check_in, late_minutes, is_present)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_id, today, check_in_time, late_minutes, True))

    conn.commit()
    conn.close()
    return jsonify({"message": "Checked in", "late_minutes": late_minutes})


# -----------------------
# ⏳ Check-Out
# -----------------------
@user_bp.route("/check-out", methods=["POST"])
def check_out():
    data = request.get_json()
    user_id = data.get("user_id")
    now = datetime.now()
    today = now.date()
    check_out_time = now.time()

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM attendance WHERE user_id = %s AND date = %s", (user_id, today))
    record = cursor.fetchone()

    if not record:
        conn.close()
        return jsonify({"message": "Check-in first"}), 400
    if record["check_out"]:
        conn.close()
        return jsonify({"message": "Already checked out"}), 400

    early_limit = time(17, 50)
    early_minutes = 0
    if check_out_time < early_limit:
        early_minutes = (datetime.combine(today, early_limit) - datetime.combine(today, check_out_time)).seconds // 60

    cursor.execute("""
        UPDATE attendance SET check_out = %s, early_minutes = %s
        WHERE user_id = %s AND date = %s
    """, (check_out_time, early_minutes, user_id, today))

    conn.commit()
    conn.close()
    return jsonify({"message": "Checked out", "early_minutes": early_minutes})
