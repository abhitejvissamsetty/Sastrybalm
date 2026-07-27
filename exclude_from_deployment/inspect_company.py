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
        cursor.execute("SELECT * FROM company_profiles")
        rows = cursor.fetchall()
        print("DATABASE COMPANY PROFILES:")
        for r in rows:
            print(f"- ID: {r['id']}, Name: {r['name']}, Code: {r['code']}")
            print(f"  ZAP URL: {r.get('zap_base_url')}, Backend: {r.get('zap_backend_company')}")
            print(f"  CMMS URL: {r.get('cmms_base_url')}, Backend: {r.get('cmms_backend_company')}")
            print(f"  CONNECT URL: {r.get('connect_base_url')}, Backend: {r.get('connect_backend_company')}")
            print(f"  Tags: {r.get('tags')}")
finally:
    conn.close()
