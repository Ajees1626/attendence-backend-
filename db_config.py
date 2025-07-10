import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()  # Load values from .env

def get_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DB", "pixdot")
    )
