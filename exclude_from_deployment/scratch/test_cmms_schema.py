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
        if not profile:
            print("Company not found")
            return
        
        cmms_key = decrypt(profile.cmms_api_key_encrypted)
        headers = {
            "Authorization": f"token {cmms_key}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=15) as client:
            # Fetch DocType metadata for Asset Capitalization
            url = f"{profile.cmms_base_url}/api/method/frappe.desk.form.load.getdoc"
            params = {
                "doctype": "Asset Capitalization",
                "name": "Asset Capitalization"
            }
            try:
                resp = await client.get(url, headers=headers, params=params)
                print(f"Fetch Asset Capitalization form schema status: {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    docs = data.get("docs", [])
                    if docs:
                        fields = docs[0].get("fields", [])
                        print("\nAsset Capitalization Fields:")
                        for f in fields:
                            if f.get("reqd"):
                                print(f"  * {f['fieldname']} ({f['fieldtype']}) - REQUIRED")
                            else:
                                print(f"    {f['fieldname']} ({f['fieldtype']})")
                    else:
                        print("No docs returned in form load")
                else:
                    print(resp.text)
            except Exception as e:
                print(f"Error fetching DocType: {e}")
                
            # Let's also fetch a list of Asset Capitalizations if any exist to see examples
            url_list = f"{profile.cmms_base_url}/api/resource/Asset Capitalization"
            try:
                resp = await client.get(url_list, headers=headers, params={"limit": 3})
                print(f"\nFetch list status: {resp.status_code}")
                print(resp.json())
            except Exception as e:
                print(f"Error listing: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
