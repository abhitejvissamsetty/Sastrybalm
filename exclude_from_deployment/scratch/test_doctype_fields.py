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
            url = f"{profile.cmms_base_url}/api/resource/DocType/Asset Capitalization"
            resp = await client.get(url, headers=headers)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                fields = data.get("data", {}).get("fields", [])
                print("Asset Capitalization Fields:")
                for f in fields:
                    req = "REQUIRED" if f.get("reqd") else "optional"
                    print(f"  - {f['fieldname']} ({f['fieldtype']}) - {req}")
            else:
                print(resp.text)
                
            # Also fetch DocType Material Request
            url_mr = f"{profile.cmms_base_url}/api/resource/DocType/Material Request"
            resp_mr = await client.get(url_mr, headers=headers)
            print(f"\nMaterial Request DocType Status: {resp_mr.status_code}")
            if resp_mr.status_code == 200:
                data_mr = resp_mr.json()
                fields_mr = data_mr.get("data", {}).get("fields", [])
                print("Material Request Fields:")
                for f in fields_mr:
                    if f.get("fieldname") in ["material_request_type", "company", "custom_location", "custom_raised_by", "items"]:
                        req = "REQUIRED" if f.get("reqd") else "optional"
                        print(f"  - {f['fieldname']} ({f['fieldtype']}) - {req}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
