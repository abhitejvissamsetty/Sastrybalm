import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

conn = pymysql.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 8889)),
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    database=os.getenv("DB_NAME", "safar_db")
)

try:
    with conn.cursor() as cursor:
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print("TABLES IN DB:")
        for t in tables:
            print(t[0])
            
        # Get schema of beats table
        cursor.execute("DESCRIBE beats")
        print("\nBEATS SCHEMA:")
        for col in cursor.fetchall():
            print(col)
            
        # Get schema of outlets table
        cursor.execute("DESCRIBE outlets")
        print("\nOUTLETS SCHEMA:")
        for col in cursor.fetchall():
            print(col)
            
        # Get schema of beat_outlets or similar mapping table if it exists
        cursor.execute("SHOW TABLES LIKE '%beat%'")
        for t in cursor.fetchall():
            print(f"\nDESCRIBE {t[0]}:")
            cursor.execute(f"DESCRIBE {t[0]}")
            for col in cursor.fetchall():
                print(col)
finally:
    conn.close()
