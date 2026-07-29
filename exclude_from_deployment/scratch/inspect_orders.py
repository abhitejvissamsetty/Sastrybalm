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
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("""
            SELECT id, order_number, status, flow_type, sync_status, connect_ref, sync_error, created_at 
            FROM orders 
            ORDER BY created_at DESC 
            LIMIT 20
        """)
        rows = cursor.fetchall()
        print("LATEST ORDERS SYNC STATUS:")
        if not rows:
            print("No orders found in database.")
        for r in rows:
            print(f"- Order: {r['order_number']} (ID: {r['id']})")
            print(f"  Status: {r['status']}, Flow Type: {r['flow_type']}")
            print(f"  Sync Status: {r['sync_status']}, Connect Ref: {r.get('connect_ref')}")
            if r.get('sync_error'):
                print(f"  Sync Error: {r['sync_error']}")
            print(f"  Created At: {r['created_at']}")
            print("-" * 50)
finally:
    conn.close()
