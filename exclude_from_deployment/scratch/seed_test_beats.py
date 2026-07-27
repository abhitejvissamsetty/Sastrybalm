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
    with conn.cursor() as cursor:
        # Check/create default geography first if not exists
        cursor.execute("SELECT id FROM geographies LIMIT 1")
        geo = cursor.fetchone()
        if not geo:
            cursor.execute(
                "INSERT INTO geographies (name, code, level, is_active) "
                "VALUES ('Hyderabad Central', 'HYD-CEN', 'territory', 1)"
            )
            conn.commit()
            cursor.execute("SELECT LAST_INSERT_ID()")
            geo_id = cursor.fetchone()[0]
        else:
            geo_id = geo[0]

        # Check/create position if not exists
        cursor.execute("SELECT id FROM positions LIMIT 1")
        pos = cursor.fetchone()
        if not pos:
            cursor.execute(
                "INSERT INTO positions (name, code, is_active) "
                "VALUES ('Field Representative', 'REP-001', 1)"
            )
            conn.commit()
            cursor.execute("SELECT LAST_INSERT_ID()")
            pos_id = cursor.fetchone()[0]
        else:
            pos_id = pos[0]

        # Map user 6 (john_rep) to this position in user_positions
        cursor.execute("SELECT * FROM user_positions WHERE user_id = 6")
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO user_positions (user_id, position_id) "
                "VALUES (6, %s)", (pos_id,)
            )
            conn.commit()
            print("Mapped user 6 to position.")

        # Create Beat 5
        cursor.execute("SELECT id FROM beats WHERE id = 5")
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO beats (id, name, code, beat_type, territory_id, is_active) "
                "VALUES (5, 'Koti Pharmacy Market', 'BEAT-KOTI-05', 'GT', %s, 1)",
                (geo_id,)
            )
            conn.commit()
            print("Seeded Beat 5.")
        else:
            print("Beat 5 already exists.")

        # Map position to beat 5
        cursor.execute("SELECT * FROM position_beats WHERE position_id = %s AND beat_id = 5", (pos_id,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO position_beats (position_id, beat_id) "
                "VALUES (%s, 5)", (pos_id,)
            )
            conn.commit()
            print("Mapped position to Beat 5.")

        # Seed Outlets under Beat 5
        outlets = [
            ("Apollo Pharmacy - Koti", "OUT-AP-01", "Mr. Rajesh Kumar", "9876543210", "Koti Cross Roads, Hyderabad", 17.3852, 78.4869),
            ("MedPlus - Sultan Bazar", "OUT-MP-02", "Mr. Srinivas Rao", "9876543211", "Sultan Bazar Main Road, Hyderabad", 17.3848, 78.4865),
            ("Venkateshwara Medical Hall", "OUT-VM-03", "Mr. Ram Reddy", "9876543212", "Chaderghat Road, Koti, Hyderabad", 17.3900, 78.4900),
        ]

        for name, code, owner, mobile, address, lat, lng in outlets:
            cursor.execute("SELECT id FROM outlets WHERE code = %s", (code,))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO outlets (name, code, owner_name, mobile, address, channel, beat_id, territory_id, gps_lat, gps_lng, status, is_active) "
                    "VALUES (%s, %s, %s, %s, %s, 'GT', 5, %s, %s, %s, 'active', 1)",
                    (name, code, owner, mobile, address, geo_id, lat, lng)
                )
                print(f"Seeded outlet {name}.")
        conn.commit()
        print("Successfully completed seeding beats and outlets!")

finally:
    conn.close()
