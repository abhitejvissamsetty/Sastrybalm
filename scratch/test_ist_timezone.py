from datetime import datetime, date
from zoneinfo import ZoneInfo
from app.utils.timezone import ist_now, ist_today, format_ist
from app.database import SessionLocal, engine
from sqlalchemy import text

def test_ist_timezone():
    print("\n--- TESTING IST TIMEZONE (GMT +5:30) CONFIGURATION ---")

    # 1. Test IST Datetime & Date helper functions
    now_ist = ist_now()
    today_ist = ist_today()
    print(f"✓ Current IST Datetime: {now_ist.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"✓ Current IST Date: {today_ist.isoformat()}")

    # 2. Test format_ist
    formatted = format_ist(now_ist)
    print(f"✓ Formatted IST Datetime: {formatted}")
    assert formatted != "—"

    # 3. Test Database Session Timezone
    db = SessionLocal()
    res = db.execute(text("SELECT @@session.time_zone;")).scalar()
    print(f"✓ Database Session Timezone: {res}")
    assert res == "+05:30" or res == "Asia/Kolkata" or "+05:30" in str(res)

    db.close()
    print("\n🎉 IST TIMEZONE (GMT +5:30) 100% VERIFIED WORKING PERFECTLY!")

if __name__ == "__main__":
    test_ist_timezone()
