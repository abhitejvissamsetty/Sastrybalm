import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.database import SessionLocal
from app.models.company import CompanyProfile
from app.utils.encryption import encrypt, decrypt
from app.adapters.connect import ConnectAdapter
import httpx

async def test_provided_key():
    api_key_raw = "c745b018621a7fe:2e527efda083985"
    base_url = "https://connect.staging.sravie.in"
    
    print("==================================================")
    print("🔌 TESTING CONNECT ENDPOINT WITH NEW CREDENTIALS")
    print("==================================================")
    print(f"Base URL: {base_url}")
    print(f"Provided API Key (raw): {api_key_raw}")
    
    # 1. Update Database (ID 1)
    db = SessionLocal()
    try:
        profile = db.query(CompanyProfile).filter(CompanyProfile.id == 1).first()
        if not profile:
            print("❌ Company profile with ID 1 not found in DB!")
            return
            
        encrypted_key = encrypt(api_key_raw)
        profile.connect_api_key_encrypted = encrypted_key
        profile.connect_base_url = base_url
        
        # Add CONNECT-READY, ensure no CONNECT-ERROR
        tags = profile.get_tags()
        if "CONNECT-READY" not in tags:
            tags.append("CONNECT-READY")
        if "CONNECT-ERROR" in tags:
            tags.remove("CONNECT-ERROR")
        profile.set_tags(tags)
        
        db.commit()
        print("✅ Database updated with encrypted credentials and URL.")
        
        # 2. Retrieve back and test
        db.refresh(profile)
        decrypted_key = decrypt(profile.connect_api_key_encrypted)
        print(f"Verified Decrypted Key from DB: {decrypted_key}")
        
        # 3. Instantiate ConnectAdapter
        adapter = ConnectAdapter(base_url=profile.connect_base_url, api_key=decrypted_key)
        
        # 4. Test Connection
        print("\n--- Testing Connection via Adapter ---")
        ok = await adapter.test_connection()
        print(f"test_connection() result: {ok}")
        
        # 5. Fetch Logged User info
        headers = adapter.get_headers()
        print(f"Headers: {headers}")
        
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{profile.connect_base_url}/api/method/frappe.auth.get_logged_user", headers=headers)
            print(f"get_logged_user status: {resp.status_code}")
            print(f"get_logged_user response: {resp.text}")
            
            # Fetch active connect items
            try:
                resp_items = await client.get(f"{profile.connect_base_url}/api/resource/Connect%20Item", headers=headers)
                print(f"Connect Item resources status: {resp_items.status_code}")
                print(f"Connect Item resources response (truncated): {resp_items.text[:500]}")
            except Exception as e:
                print(f"Failed to fetch Connect Items: {e}")
                
    except Exception as e:
        print(f"❌ Error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_provided_key())
