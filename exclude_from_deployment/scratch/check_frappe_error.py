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
            # Test create location and print exception
            url_loc = f"{profile.cmms_base_url}/api/resource/Location"
            resp = await client.post(url_loc, headers=headers, json={"data": {"location_name": "Test Location"}})
            print("Location Creation Response:")
            print(resp.status_code)
            print(resp.text)
            
            # Test create item and print exception
            url_item = f"{profile.cmms_base_url}/api/resource/Item"
            svc_payload = {
                "item_code": "Installation Service",
                "item_name": "Installation Service",
                "item_group": "Consumable",
                "stock_uom": "Nos",
                "is_fixed_asset": 0,
                "is_stock_item": 0
            }
            resp_item = await client.post(url_item, headers=headers, json={"data": svc_payload})
            print("\nItem Creation Response:")
            print(resp_item.status_code)
            print(resp_item.text)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
