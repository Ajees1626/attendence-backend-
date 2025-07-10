# salary_model.py

from db import get_connection
from calendar import monthrange

# Salary rules (can be customized per user in future)
SALARY_PER_DAY = 1000
PAID_LEAVE_DAYS = 1
PERMISSION_MINUTES = 120
LATE_CUT_PERCENT = 20
EARLY_CUT_PERCENT = 20
BONUS_DAY_PAY = 1  # if perfect attendance

def calculate_salary_for_user(user_id, year, month):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Get number of days in the month
    days_in_month = monthrange(year, month)[1]
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{days_in_month:02d}"

    # Fetch attendance records
    cursor.execute("""
        SELECT * FROM attendance
        WHERE user_id = %s AND date BETWEEN %s AND %s
    """, (user_id, start_date, end_date))
    records = cursor.fetchall()

    # Initialize counters
    present_days = 0
    paid_leave = 0
    permission_used = 0
    late_deduct = 0
    early_deduct = 0
    bonus = 0

    for rec in records:
        present_days += 1

        if rec.get("is_paid_leave"):
            paid_leave += 1

        if rec.get("permission_used"):
            permission_used += 1

        if rec.get("late_minutes", 0) > 10:
            late_deduct += SALARY_PER_DAY * (LATE_CUT_PERCENT / 100)

        if rec.get("early_minutes", 0) > 10:
            early_deduct += SALARY_PER_DAY * (EARLY_CUT_PERCENT / 100)

    total_base_salary = present_days * SALARY_PER_DAY

    # Unpaid Leave Deduction
    unpaid_leaves = max(0, paid_leave - PAID_LEAVE_DAYS)
    unpaid_leave_deduct = unpaid_leaves * SALARY_PER_DAY

    # Permission Deduction
    total_permission_minutes = permission_used * 60
    excess_permission = max(0, total_permission_minutes - PERMISSION_MINUTES)
    permission_deduct = (excess_permission / 60) * SALARY_PER_DAY

    # Bonus Calculation
    if present_days == days_in_month and paid_leave == 0 and permission_used == 0:
        bonus = SALARY_PER_DAY * BONUS_DAY_PAY

    total_deductions = late_deduct + early_deduct + unpaid_leave_deduct + permission_deduct
    final_salary = total_base_salary - total_deductions + bonus

    # Insert or Update salary table
    cursor.execute("""
        INSERT INTO salary (
            user_id, month, year, total_days, total_present,
            paid_leave, permissions_used, late_deductions,
            early_deductions, total_deductions, total_additions, final_salary
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            total_days = VALUES(total_days),
            total_present = VALUES(total_present),
            paid_leave = VALUES(paid_leave),
            permissions_used = VALUES(permissions_used),
            late_deductions = VALUES(late_deductions),
            early_deductions = VALUES(early_deductions),
            total_deductions = VALUES(total_deductions),
            total_additions = VALUES(total_additions),
            final_salary = VALUES(final_salary)
    """, (
        user_id, month, year, days_in_month, present_days, paid_leave,
        permission_used, late_deduct, early_deduct,
        total_deductions, bonus, final_salary
    ))

    conn.commit()
    conn.close()

    return {
        "user_id": user_id,
        "month": month,
        "year": year,
        "days_in_month": days_in_month,
        "present_days": present_days,
        "paid_leave_used": paid_leave,
        "permission_used": permission_used,
        "late_deductions": late_deduct,
        "early_deductions": early_deduct,
        "unpaid_leave_deduct": unpaid_leave_deduct,
        "permission_deduct": permission_deduct,
        "total_deductions": total_deductions,
        "bonus": bonus,
        "final_salary": final_salary
    }
