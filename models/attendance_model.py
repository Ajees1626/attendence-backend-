from db import get_connection
from datetime import datetime, time
import psycopg2.extras


# Calculate late minutes
def calculate_late_minutes(check_in_time):
    late_limit = time(9, 40)
    if check_in_time <= late_limit:
        return 0
    delta = datetime.combine(datetime.today(), check_in_time) - datetime.combine(datetime.today(), late_limit)
    return delta.seconds // 60


# Calculate early leave minutes
def calculate_early_minutes(check_out_time):
    early_limit = time(17, 50)
    if check_out_time >= early_limit:
        return 0
    delta = datetime.combine(datetime.today(), early_limit) - datetime.combine(datetime.today(), check_out_time)
    return delta.seconds // 60


# Check if user already checked in today
def is_already_checked_in(user_id, today):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM attendance WHERE user_id = %s AND date = %s", (user_id, today))
    result = cursor.fetchone()
    conn.close()
    return result


# Perform check-in
def perform_check_in(user_id):
    now = datetime.now()
    today = now.date()
    check_in_time = now.time()
    late_minutes = calculate_late_minutes(check_in_time)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO attendance (user_id, date, check_in, late_minutes, is_present)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_id, today, check_in_time, late_minutes, True))
    conn.commit()
    conn.close()

    return {
        "check_in_time": str(check_in_time),
        "late_minutes": late_minutes
    }


# Perform check-out
def perform_check_out(user_id):
    now = datetime.now()
    today = now.date()
    check_out_time = now.time()
    early_minutes = calculate_early_minutes(check_out_time)

    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Fetch check-in record
    cursor.execute("SELECT * FROM attendance WHERE user_id = %s AND date = %s", (user_id, today))
    record = cursor.fetchone()

    if not record:
        conn.close()
        return {"error": "No check-in found for today"}, 404

    if record["check_out"]:
        conn.close()
        return {"error": "Already checked out"}, 400

    cursor.execute("""
        UPDATE attendance
        SET check_out = %s, early_minutes = %s
        WHERE user_id = %s AND date = %s
    """, (check_out_time, early_minutes, user_id, today))
    conn.commit()
    conn.close()

    return {
        "check_out_time": str(check_out_time),
        "early_minutes": early_minutes
    }


# Get full attendance log
def get_attendance_log(user_id):
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
    return logs
