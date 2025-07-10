# user_model.py

from db import get_connection
import psycopg2.extras
import bcrypt

# Get user by email (for login)
def get_user_by_email(email):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    conn.close()
    return user

# Verify password (hashed)
def verify_password(input_password, stored_hash):
    return bcrypt.checkpw(input_password.encode(), stored_hash.encode())

# Get user by ID
def get_user_by_id(user_id):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

# Register new user (admin/staff)
def register_user(name, email, phone, age, batch, salary, role="user", password="123456"):
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (name, email, phone, age, batch, salary_per_month, role, password)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (name, email, phone, age, batch, salary, role, hashed_password))
    conn.commit()
    conn.close()

# Get all staff users
def get_all_staff():
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT * FROM users WHERE role = 'user'")
    result = cursor.fetchall()
    conn.close()
    return result
