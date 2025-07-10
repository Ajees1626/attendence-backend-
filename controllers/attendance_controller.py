from flask import Blueprint, request, jsonify
from db import get_connection
from datetime import datetime, time
import psycopg2.extras

attendance_bp = Blueprint('attendance', __name__)

# Utility: calculate late/early minutes
def get_minutes_late(checkin_time):
    threshold = time(9, 30)
    late_limit = time(9, 40)

    if checkin_time <= threshold:
        return 0
    elif checkin_time <= late_limit:
        return 0  # grace period
    else:
        delta = datetime.combine(datetime.today(), checkin_time) - datetime.combine(datetime.today(), late_limit)
        return delta.seconds // 60  # late minutes

def get_minutes_early(checkout_time):
    limit = time(17, 50)
    if checkout_time >= limit:
        return 0
    delta = datetime.combine(datetime.today(), limit) - datetime.combine(datetime.today(), checkout_time)
    return delta.seconds // 60  # early minutes

# ✅ Check-in
@attendance_bp.route("/check-in", methods=["POST"])
def check_in():
    data = request.get_json()
    user_id = data.get("user_id")
    now = datetime.now()
    today = now.date()
    check_in_time = now.time()

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Check if already checked in
    cursor.execute("SELECT * FROM attendance WHERE user_id = %s AND date = %s", (user_id, today))
    row = cursor.fetchone()

    if row:
        return jsonify({"message": "Already checked in."}), 400

    late_min = get_minutes_late(check_in_time)
    cursor.execute("""
        INSERT INTO attendance (user_id, date, check_in, late_minutes, is_present)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_id, today, check_in_time, late_min, True))

    conn.commit()
    conn.close()

    return jsonify({"message": "Checked in successfully", "late_minutes": late_min})


# ✅ Check-out
@attendance_bp.route("/check-out", methods=["POST"])
def check_out():
    data = request.get_json()
    user_id = data.get("user_id")
    now = datetime.now()
    today = now.date()
    check_out_time = now.time()

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT * FROM attendance WHERE user_id = %s AND date = %s", (user_id, today))
    row = cursor.fetchone()

    if not row:
        return jsonify({"message": "You must check-in first."}), 400

    if row["check_out"]:
        return jsonify({"message": "Already checked out."}), 400

    early_min = get_minutes_early(check_out_time)

    cursor.execute("""
        UPDATE attendance SET check_out = %s, early_minutes = %s
        WHERE user_id = %s AND date = %s
    """, (check_out_time, early_min, user_id, today))

    conn.commit()
    conn.close()

    return jsonify({"message": "Checked out successfully", "early_minutes": early_min})
