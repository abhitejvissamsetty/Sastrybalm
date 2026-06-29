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
            # 1. Fetch Locations
            url_loc = f"{profile.cmms_base_url}/api/resource/Location"
            resp_loc = await client.get(url_loc, headers=headers, params={"limit": 10})
            print("Locations on CMMS Staging:")
            print(resp_loc.json())
            
            # 2. Fetch Items
            url_item = f"{profile.cmms_base_url}/api/resource/Item"
            resp_item = await client.get(url_item, headers=headers, params={"limit": 10})
            print("\nItems on CMMS Staging:")
            print(resp_item.json())
            
            # 3. Fetch Warehouses
            url_wh = f"{profile.cmms_base_url}/api/resource/Warehouse"
            resp_wh = await client.get(url_wh, headers=headers, params={"limit": 10})
            print("\nWarehouses on CMMS Staging:")
            print(resp_wh.json())
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
