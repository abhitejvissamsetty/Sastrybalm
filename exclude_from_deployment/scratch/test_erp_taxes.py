import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.database import SessionLocal
from app.models.company import CompanyProfile
from app.utils.encryption import decrypt
from app.adapters.zap import ZapAdapter
import httpx
import json
import asyncio

async def main():
    db = SessionLocal()
    try:
        profile = db.query(CompanyProfile).filter(CompanyProfile.id == 1).first()
        api_key = decrypt(profile.zap_api_key_encrypted)
        zap = ZapAdapter(
            base_url=profile.zap_base_url,
            api_key=api_key
        )
        
        # Fetch items first without gst_rate
        params = {
            "fields": json.dumps(["name", "item_name", "item_code", "item_group", "standard_rate"]),
            "filters": json.dumps([
                ["has_variants", "=", 0],
                ["item_group", "=", "Products"],
                ["disabled", "=", 0],
                ["Item Default", "company", "=", profile.zap_backend_company]
            ]),
            "limit_page_length": 5,
        }
        
        async with httpx.AsyncClient(timeout=15) as client:
            headers = zap.get_auth_headers("integration")
            url = f"{profile.zap_base_url}/api/resource/Item"
            resp = await client.get(url, headers=headers, params=params)
            print(f"List items status: {resp.status_code}")
            if resp.status_code != 200:
                print(resp.text)
                return
                
            items = resp.json().get("data", [])
            print(f"Fetched {len(items)} items. Example item:")
            if not items:
                print("No items found.")
                return
            print(json.dumps(items[0], indent=2))
            
            # Now fetch the detail of the first item
            item_code = items[0]["name"]
            detail_url = f"{profile.zap_base_url}/api/resource/Item/{item_code}"
            detail_resp = await client.get(detail_url, headers=headers)
            print(f"\nDetail for {item_code} status: {detail_resp.status_code}")
            if detail_resp.status_code == 200:
                detail_data = detail_resp.json().get("data", {})
                # print the taxes table and default taxes if any
                print("Taxes field value:")
                print(json.dumps(detail_data.get("taxes"), indent=2))
            else:
                print(detail_resp.text)
                
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
