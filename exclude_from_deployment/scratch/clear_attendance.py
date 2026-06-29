import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

conn = pymysql.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 8889)),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", "root"),
    database=os.getenv("DB_NAME", "sastrybalm_db")
)

try:
    with conn.cursor() as cursor:
        cursor.execute("SHOW TABLES")
        tables = [r[0] for r in cursor.fetchall()]
        print("DATABASE TABLES:", tables)
        
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        if "visit_records" in tables:
            cursor.execute("TRUNCATE TABLE visit_records")
            print("Cleared visit_records.")
            
        if "timesheets" in tables:
            cursor.execute("TRUNCATE TABLE timesheets")
            print("Cleared timesheets.")
            
        # Let's see if we have 'attendance' or other table names
        for t in ["attendance", "attendances", "attendance_logs"]:
            if t in tables:
                cursor.execute(f"TRUNCATE TABLE {t}")
                print(f"Cleared {t}.")
                
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        print("ATTENDANCE DATA CLEARED FRESH.")
finally:
    conn.close()
