import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app.models.company import CompanyProfile
from app.utils.encryption import decrypt
import httpx
import asyncio

async def main():
    db = SessionLocal()
    try:
        profile = db.query(CompanyProfile).filter(CompanyProfile.id == 1).first()
        cmms_key = decrypt(profile.cmms_api_key_encrypted)
        headers = {
            "Authorization": f"token {cmms_key}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient(timeout=15) as client:
            url = f"{profile.cmms_base_url}/api/resource/GST HSN Code"
            resp = await client.get(url, headers=headers, params={"limit": 5})
            print("HSN Codes:")
            print(resp.json())
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
