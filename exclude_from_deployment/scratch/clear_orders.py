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
        # Turn off foreign key checks temporarily to clear cleanly
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        cursor.execute("TRUNCATE TABLE order_items")
        cursor.execute("TRUNCATE TABLE orders")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        print("ALL ORDERS AND ORDER ITEMS TRUNCATED SUCCESSFULLY.")
finally:
    conn.close()
