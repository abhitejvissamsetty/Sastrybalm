import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

conn = pymysql.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 8889)),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", "root"),
    database=os.getenv("DB_NAME", "safar_db")
)

try:
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("DESCRIBE users")
        print("USERS SCHEMA:")
        for col in cursor.fetchall():
            print(f"- {col['Field']}: {col['Type']}")
            
        cursor.execute("SHOW TABLES LIKE 'user_positions'")
        if cursor.fetchall():
            cursor.execute("DESCRIBE user_positions")
            print("\nUSER_POSITIONS SCHEMA:")
            for col in cursor.fetchall():
                print(f"- {col['Field']}: {col['Type']}")
                
        cursor.execute("SELECT * FROM positions")
        print("\nPOSITIONS:")
        for row in cursor.fetchall():
            print(row)
            
        cursor.execute("SELECT * FROM beats")
        print("\nBEATS:")
        for row in cursor.fetchall():
            print(row)

        cursor.execute("SELECT * FROM position_beats")
        print("\nPOSITION_BEATS:")
        for row in cursor.fetchall():
            print(row)
finally:
    conn.close()
