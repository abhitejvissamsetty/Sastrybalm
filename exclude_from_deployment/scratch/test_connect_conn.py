import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.database import SessionLocal
from app.models.company import CompanyProfile
from app.utils.encryption import decrypt
from app.adapters.connect import ConnectAdapter
import httpx

async def test_connect():
    db = SessionLocal()
    try:
        profile = db.query(CompanyProfile).filter(CompanyProfile.id == 1).first()
        if not profile:
            print("Company profile not found!")
            return
            
        connect_key = decrypt(profile.connect_api_key_encrypted)
        print(f"CONNECT URL: {profile.connect_base_url}")
        print(f"CONNECT Key (decrypted): {connect_key}")
        
        adapter = ConnectAdapter(base_url=profile.connect_base_url, api_key=connect_key)
        
        # Test generic connection
        ok = await adapter.test_connection()
        print(f"test_connection() result: {ok}")
        
        # Test specific get_logged_user request to see the HTTP response
        headers = adapter.get_headers()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{profile.connect_base_url}/api/method/frappe.auth.get_logged_user", headers=headers)
            print(f"get_logged_user status: {resp.status_code}")
            print(f"get_logged_user body: {resp.text}")
            
            # Let's also fetch active connect items to see if resource endpoints are open
            try:
                resp_items = await client.get(f"{profile.connect_base_url}/api/resource/Connect%20Item", headers=headers)
                print(f"Connect Item resources status: {resp_items.status_code}")
                print(f"Connect Item resources body: {resp_items.text[:500]}")
            except Exception as e:
                print(f"Failed to fetch Connect Items: {e}")
                
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_connect())
