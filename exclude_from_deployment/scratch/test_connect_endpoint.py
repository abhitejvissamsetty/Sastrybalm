import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.database import SessionLocal
from app.routers.company import profile_test_connect

async def run_test():
    print("==================================================")
    print("🧪 TESTING ROUTER ENDPOINT (profile_test_connect)")
    print("==================================================")
    
    db = SessionLocal()
    try:
        res = await profile_test_connect(profile_id=1, current_user=None, db=db)
        print("Endpoint Response:")
        import json
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"❌ Error calling endpoint: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_test())
