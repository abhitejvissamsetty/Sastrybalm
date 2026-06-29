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
        headers = zap.get_auth_headers("integration")
        
        # Attempt 1: try fetching "taxes" in the fields list directly
        params_with_taxes = {
            "fields": json.dumps(["name", "item_name", "item_code", "item_group", "standard_rate", "taxes"]),
            "filters": json.dumps([
                ["has_variants", "=", 0],
                ["item_group", "=", "Products"],
                ["disabled", "=", 0],
                ["Item Default", "company", "=", profile.zap_backend_company]
            ]),
            "limit_page_length": 3,
        }
        
        async with httpx.AsyncClient(timeout=15) as client:
            url = f"{profile.zap_base_url}/api/resource/Item"
            resp = await client.get(url, headers=headers, params=params_with_taxes)
            print(f"[Attempt 1 - 'taxes' in fields list] Status: {resp.status_code}")
            if resp.status_code == 200:
                items = resp.json().get("data", [])
                print(f"Fetched {len(items)} items. First item:")
                if items:
                    print(json.dumps(items[0], indent=2))
            else:
                print(f"Error: {resp.text[:400]}")
        
        print("\n---\n")
        
        # Attempt 2: try fetching with wildcard taxes.*
        params_wildcard = {
            "fields": json.dumps(["name", "item_name", "item_code", "item_group", "standard_rate", "taxes.item_tax_template", "taxes.tax_rate"]),
            "filters": json.dumps([
                ["has_variants", "=", 0],
                ["item_group", "=", "Products"],
                ["disabled", "=", 0],
                ["Item Default", "company", "=", profile.zap_backend_company]
            ]),
            "limit_page_length": 3,
        }
        
        async with httpx.AsyncClient(timeout=15) as client:
            url = f"{profile.zap_base_url}/api/resource/Item"
            resp2 = await client.get(url, headers=headers, params=params_wildcard)
            print(f"[Attempt 2 - 'taxes.item_tax_template' in fields list] Status: {resp2.status_code}")
            if resp2.status_code == 200:
                items2 = resp2.json().get("data", [])
                print(f"Fetched {len(items2)} items. First item:")
                if items2:
                    print(json.dumps(items2[0], indent=2))
            else:
                print(f"Error: {resp2.text[:400]}")
                
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
