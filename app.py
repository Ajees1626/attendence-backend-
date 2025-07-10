from flask import Flask, request, jsonify
from flask_cors import CORS
from db import get_connection
from datetime import datetime
from dotenv import load_dotenv
import bcrypt
import random
import string
import os
import psycopg2.extras

load_dotenv()

app = Flask(__name__)
CORS(app)

def generate_password(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"success": False, "message": "Email and password are required"}), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, email, role, image, password FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    conn.close()

    if user and bcrypt.checkpw(password.encode(), user["password"].encode()):
        return jsonify({
            "success": True,
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"],
                "image": user.get("image")  # 👈 includes image
            }
        })
    return jsonify({"success": False, "message": "Invalid credentials"}), 401


@app.route('/api/add-staff', methods=['POST'])
def add_staff():
    data = request.json
    password = generate_password()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (name, email, phone, age, batch, salary, password, role)
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'user')
    """, (
        data['name'], data['email'], data['phone'], data.get('age'),
        data.get('batch'), data['salary'], password
    ))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Staff added successfully", "password": password})

@app.route('/admin/staff', methods=['GET'])
def all_staff():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE role='user'")
    result = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(result)

@app.route('/admin/total-salary', methods=['GET'])
def total_salary():
    now = datetime.now()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT SUM(final_salary) AS total FROM salary_logs WHERE month=%s AND year=%s", (now.month, now.year))
    result = cur.fetchone()
    cur.close()
    conn.close()
    return jsonify({"total": float(result[0]) if result[0] else 0})

@app.route('/user/checkin', methods=['POST'])
def checkin():
    data = request.get_json()
    user_id = data['user_id']
    now = datetime.now()
    today = now.date()
    time_now = now.time()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM attendance WHERE user_id=%s AND date=%s", (user_id, today))
    already = cur.fetchone()
    if already:
        return jsonify({"message": "Already checked in today."}), 400
    late = time_now > datetime.strptime("09:30", "%H:%M").time()
    cur.execute("INSERT INTO attendance (user_id, date, checkin_time, is_late) VALUES (%s, %s, %s, %s)",
                (user_id, today, time_now, late))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Check-in successful", "late": late})

@app.route('/user/checkout', methods=['POST'])
def checkout():
    data = request.get_json()
    user_id = data['user_id']
    now = datetime.now()
    today = now.date()
    time_now = now.time()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM attendance WHERE user_id=%s AND date=%s", (user_id, today))
    record = cur.fetchone()
    if not record:
        return jsonify({"message": "Check-in not found."}), 404
    if record[3]:
        return jsonify({"message": "Already checked out today."}), 400
    early = time_now < datetime.strptime("18:00", "%H:%M").time()
    cur.execute("UPDATE attendance SET checkout_time=%s, is_early_leave=%s WHERE user_id=%s AND date=%s",
                (time_now, early, user_id, today))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Check-out successful", "early_leave": early})

@app.route('/admin/calculate-salary', methods=['POST'])
def calculate_salary():
    data = request.get_json()
    month = data['month']
    year = data['year']
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, salary AS salary_per_month FROM users WHERE role='user'")
    users = cur.fetchall()
    for user in users:
        uid = user['id']
        monthly_salary = float(user['salary_per_month'])
        per_day = monthly_salary / 30
        cur.execute("SELECT * FROM attendance WHERE user_id=%s AND EXTRACT(MONTH FROM date)=%s AND EXTRACT(YEAR FROM date)=%s",
                    (uid, month, year))
        logs = cur.fetchall()
        late_deduction = early_deduction = 0
        for log in logs:
            if log['is_late']:
                late_deduction += per_day * 0.2
            if log['is_early_leave']:
                early_deduction += per_day * 0.2
        total_cut = late_deduction + early_deduction
        final = monthly_salary - total_cut
        cur.execute("""
            INSERT INTO salary_logs (user_id, month, year, base_salary, late_deductions, early_deductions, final_salary)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (uid, month, year, monthly_salary, late_deduction, early_deduction, final))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"message": "Salary calculated for all users"})

@app.route('/api/user-attendance/<int:user_id>', methods=['GET'])
def get_user_attendance(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT date, checkin_time, checkout_time, is_late, is_early_leave
        FROM attendance
        WHERE user_id = %s
        ORDER BY date DESC
    """, (user_id,))
    rows = cur.fetchall()
    result = [
        {
            "date": row[0].strftime("%Y-%m-%d"),
            "checkin_time": str(row[1]) if row[1] else "-",
            "checkout_time": str(row[2]) if row[2] else "-",
            "is_late": row[3],
            "is_early_leave": row[4],
        }
        for row in rows
    ]
    cur.close()
    conn.close()
    return jsonify(result)

@app.route('/api/user-salary/<int:user_id>', methods=['GET'])
def get_user_salary(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT month, year, base_salary, late_deductions, early_deductions, final_salary
        FROM salary_logs
        WHERE user_id = %s
        ORDER BY year DESC, month DESC
        LIMIT 1
    """, (user_id,))
    result = cur.fetchone()
    cur.close()
    conn.close()
    if not result:
        return jsonify({"error": "No salary record found"}), 404
    return jsonify({
        "month": result[0],
        "year": result[1],
        "base_salary": float(result[2]),
        "late_deductions": float(result[3]),
        "early_deductions": float(result[4]),
        "final_salary": float(result[5])
    })

@app.route('/api/staff', methods=['GET'])
def get_staff():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, email, phone, age, batch, salary, role FROM users WHERE role='user'")
    rows = cur.fetchall()
    result = [
        {
            "id": row[0], "name": row[1], "email": row[2],
            "phone": row[3], "age": row[4], "batch": row[5],
            "salary": float(row[6]), "status": row[7]
        }
        for row in rows
    ]
    cur.close()
    conn.close()
    return jsonify(result)

@app.route('/api/salary-report', methods=['GET'])
def salary_report():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.name, s.base_salary, s.late_deductions + s.early_deductions AS total_deductions, s.final_salary
        FROM salary_logs s
        JOIN users u ON s.user_id = u.id
        WHERE s.month = EXTRACT(MONTH FROM CURRENT_DATE) AND s.year = EXTRACT(YEAR FROM CURRENT_DATE)
    """)
    rows = cur.fetchall()
    total_spent = sum(float(row[3]) for row in rows)
    report = [
        {
            "name": row[0],
            "base_salary": float(row[1]),
            "total_deductions": float(row[2]),
            "final_salary": float(row[3])
        }
        for row in rows
    ]
    cur.close()
    conn.close()
    return jsonify({"report": report, "total_spent": total_spent})

@app.route("/test")
def test():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users")
    data = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True)