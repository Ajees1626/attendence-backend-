# salary_calc.py

from db import get_connection
from calendar import monthrange
from datetime import datetime

# Configurable constants
SALARY_PER_DAY = 1000
PAID_LEAVE_DAYS = 1
PERMISSION_MINUTES_LIMIT = 120
LATE_CUT_PERCENT = 20
EARLY_CUT_PERCENT = 20
BONUS_IF_NO_ABSENCE = 1000

def calculate_salary_for_user(user_id, year, month):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Get total days in month
    days_in_month = monthrange(year, month)[1]
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{days_in_month:02d}"

    # Fetch attendance for user
    cursor.execute("""
        SELECT * FROM attendance 
        WHERE user_id = %s AND date BETWEEN %s AND %s
    """, (user_id, start_date, end_date))
    logs = cursor.fetchall()

    # Initialize counters
    total_present = 0
    total_permission = 0
    total_leave = 0
    late_deduction = 0
    early_deduction = 0

    for log in logs:
        total_present += 1
        late = log.get("late_minutes") or 0
        early = log.get("early_minutes") or 0
        permission = log.get("permission_used") or 0
        is_paid_leave = log.get("is_paid_leave") or False

        # Late deduction
        if late > 10:
            late_deduction += SALARY_PER_DAY * (LATE_CUT_PERCENT / 100)

        # Early checkout deduction
        if early > 10:
            early_deduction += SALARY_PER_DAY * (EARLY_CUT_PERCENT / 100)

        # Permission tracking
        if permission:
            total_permission += 1

        # Paid leave
        if is_paid_leave:
            total_leave += 1

    total_salary = total_present * SALARY_PER_DAY

    # Calculate unpaid leave deduction
    unpaid_leave_days = max(0, total_leave - PAID_LEAVE_DAYS)
    unpaid_leave_deduct = unpaid_leave_days * SALARY_PER_DAY

    # Permission deduction
    total_permission_minutes = total_permission * 60
    excess_minutes = max(0, total_permission_minutes - PERMISSION_MINUTES_LIMIT)
    permission_deduct = (excess_minutes / 60) * SALARY_PER_DAY

    # Bonus logic
    bonus = 0
    if total_present == days_in_month and total_permission == 0 and unpaid_leave_days == 0:
        bonus = BONUS_IF_NO_ABSENCE

    # Final salary
    total_deductions = late_deduction + early_deduction + unpaid_leave_deduct + permission_deduct
    final_salary = total_salary - total_deductions + bonus

    # Save result
    cursor.execute("""
        INSERT INTO salary (user_id, month, year, total_days, total_present,
        paid_leave, permissions_used, late_deductions, early_deductions, total_deductions,
        total_additions, final_salary)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
        total_days=VALUES(total_days),
        total_present=VALUES(total_present),
        paid_leave=VALUES(paid_leave),
        permissions_used=VALUES(permissions_used),
        late_deductions=VALUES(late_deductions),
        early_deductions=VALUES(early_deductions),
        total_deductions=VALUES(total_deductions),
        total_additions=VALUES(total_additions),
        final_salary=VALUES(final_salary)
    """, (
        user_id, month, year, days_in_month, total_present, total_leave, total_permission,
        late_deduction, early_deduction, total_deductions, bonus, final_salary
    ))

    conn.commit()
    conn.close()

    return {
        "user_id": user_id,
        "month": month,
        "year": year,
        "present_days": total_present,
        "paid_leave": total_leave,
        "permissions_used": total_permission,
        "late_deductions": late_deduction,
        "early_deductions": early_deduction,
        "unpaid_leave_deduct": unpaid_leave_deduct,
        "permission_deduct": permission_deduct,
        "bonus": bonus,
        "final_salary": final_salary
    }
