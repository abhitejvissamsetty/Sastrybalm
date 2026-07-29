import pymysql
from dotenv import load_dotenv
import os
import bcrypt

load_dotenv()

conn = pymysql.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 8889)),
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    database=os.getenv("DB_NAME", "safar_db")
)

try:
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("SELECT id, username, email, is_active, role, hashed_password FROM users")
        rows = cursor.fetchall()
        print("DATABASE USERS:")
        for r in rows:
            print(f"- ID: {r['id']}, Username: {r['username']}, Email: {r['email']}, Is Active: {r['is_active']}, Role: {r['role']}")
            print(f"  Hashed password: {r['hashed_password']}")
            # Test a password
            test_pw = "John@123"
            try:
                matched = bcrypt.checkpw(test_pw.encode("utf-8"), r['hashed_password'].encode("utf-8"))
                print(f"  Matches '{test_pw}': {matched}")
            except Exception as e:
                print(f"  Bcrypt check failed: {e}")
finally:
    conn.close()
