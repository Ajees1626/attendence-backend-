from flask import Blueprint, request, jsonify
from db import get_connection
from datetime import datetime
from calendar import monthrange
import psycopg2.extras

salary_bp = Blueprint('salary', __name__)

# Configs
SALARY_PER_DAY = 1000
PAID_LEAVE_DAYS = 1
PERMISSION_MINUTES = 120
LATE_CUT_PERCENT = 20
EARLY_CUT_PERCENT = 20
BONUS_DAY_PAY = 1  # if perfect attendance

@salary_bp.route("/calculate/<int:user_id>/<int:year>/<int:month>", methods=["GET"])
def calculate_salary(user_id, year, month):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Get days in the month
    days_in_month = monthrange(year, month)[1]
    month_start = f"{year}-{month:02d}-01"
    month_end = f"{year}-{month:02d}-{days_in_month:02d}"

    # Get attendance records
    cursor.execute("""
        SELECT * FROM attendance
        WHERE user_id = %s AND date BETWEEN %s AND %s
    """, (user_id, month_start, month_end))
    records = cursor.fetchall()

    # Init counters
    total_present = 0
    total_leave = 0
    total_permission = 0
    total_late_deduct = 0
    total_early_deduct = 0
    total_deduct = 0
    bonus = 0

    for record in records:
        total_present += 1

        late = record.get("late_minutes") or 0
        early = record.get("early_minutes") or 0
        permission = record.get("permission_used")

        if late > 10:
            total_late_deduct += SALARY_PER_DAY * (LATE_CUT_PERCENT / 100)

        if early > 10:
            total_early_deduct += SALARY_PER_DAY * (EARLY_CUT_PERCENT / 100)

        if permission:
            total_permission += 1

        if record.get("is_paid_leave"):
            total_leave += 1

    total_salary = total_present * SALARY_PER_DAY

    # Unpaid leave
    unpaid_leave_days = max(0, total_leave - PAID_LEAVE_DAYS)
    unpaid_leave_deduct = unpaid_leave_days * SALARY_PER_DAY

    # Permission logic
    excess_permission_minutes = max(0, (total_permission * 60) - PERMISSION_MINUTES)
    permission_deduct = (excess_permission_minutes / 60) * SALARY_PER_DAY

    # Bonus
    if total_present == days_in_month and total_leave == 0 and total_permission == 0:
        bonus = SALARY_PER_DAY * BONUS_DAY_PAY

    total_deduct = total_late_deduct + total_early_deduct + unpaid_leave_deduct + permission_deduct
    final_salary = total_salary - total_deduct + bonus

    # Save salary to DB using PostgreSQL UPSERT
    cursor.execute("""
        INSERT INTO salary (
            user_id, month, year, total_days, total_present,
            paid_leave, permissions_used, late_deductions, early_deductions,
            total_deductions, total_additions, final_salary
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, month, year) DO UPDATE SET
            total_days = EXCLUDED.total_days,
            total_present = EXCLUDED.total_present,
            paid_leave = EXCLUDED.paid_leave,
            permissions_used = EXCLUDED.permissions_used,
            late_deductions = EXCLUDED.late_deductions,
            early_deductions = EXCLUDED.early_deductions,
            total_deductions = EXCLUDED.total_deductions,
            total_additions = EXCLUDED.total_additions,
            final_salary = EXCLUDED.final_salary
    """, (
        user_id, month, year, days_in_month, total_present, total_leave, total_permission,
        total_late_deduct, total_early_deduct, total_deduct, bonus, final_salary
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "user_id": user_id,
        "month": month,
        "year": year,
        "days_in_month": days_in_month,
        "present_days": total_present,
        "paid_leave_used": total_leave,
        "permission_used": total_permission,
        "late_deductions": total_late_deduct,
        "early_deductions": total_early_deduct,
        "unpaid_leave_deduct": unpaid_leave_deduct,
        "permission_deduct": permission_deduct,
        "total_deductions": total_deduct,
        "bonus": bonus,
        "final_salary": final_salary
    })
