import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.database import SessionLocal
from app.models.company import CompanyProfile
from app.utils.encryption import decrypt
from app.adapters.cmms import CMSAdapter
import httpx
import json
import asyncio
from decimal import Decimal
from datetime import date
from app.routers.company import _extract_gst_from_taxes

async def main():
    db = SessionLocal()
    try:
        profile = db.query(CompanyProfile).filter(CompanyProfile.id == 1).first()
        cmms_key = decrypt(profile.cmms_api_key_encrypted)
        cmms = CMSAdapter(base_url=profile.cmms_base_url, api_key=cmms_key)
        headers = cmms.get_headers()
        
        async with httpx.AsyncClient(timeout=30) as client:
            # Fetch CMMS items (Consumable)
            params = {
                "fields": json.dumps(["name", "item_name", "item_code", "item_group", "standard_rate"]),
                "filters": json.dumps([
                    ["item_group", "=", "Consumable"],
                    ["disabled", "=", 0]
                ]),
                "limit_page_length": 5,
            }
            resp = await client.get(f"{profile.cmms_base_url}/api/resource/Item", headers=headers, params=params)
            print(f"List CMMS items status: {resp.status_code}")
            items = resp.json().get("data", [])
            print(f"Total CMMS items found: {len(items)}")
            
            for item in items:
                item_code = item["name"]
                detail_resp = await client.get(
                    f"{profile.cmms_base_url}/api/resource/Item/{item_code}",
                    headers=headers
                )
                if detail_resp.status_code == 200:
                    detail = detail_resp.json().get("data", {})
                    taxes = detail.get("taxes", [])
                    gst_rate = _extract_gst_from_taxes(taxes)
                    print(f"  {item_code}: MRP={item.get('standard_rate')}, GST={gst_rate}% (taxes count: {len(taxes)})")
                else:
                    print(f"  {item_code}: Failed to fetch detail ({detail_resp.status_code})")
                    
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
