import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app.models.company import CompanyProfile
from app.utils.encryption import decrypt
import httpx
import asyncio

async def test_conn():
    db = SessionLocal()
    try:
        profile = db.query(CompanyProfile).filter(CompanyProfile.id == 1).first()
        if not profile:
            print("Company profile with ID 1 not found!")
            return
        
        print(f"Company ID: {profile.id}, Name: {profile.name}, Code: {profile.code}")
        
        # ZAP
        zap_key = decrypt(profile.zap_api_key_encrypted)
        print(f"ZAP URL: {profile.zap_base_url}")
        print(f"ZAP Key (decrypted): {zap_key}")
        
        # CONNECT
        connect_key = decrypt(profile.connect_api_key_encrypted)
        print(f"CONNECT URL: {profile.connect_base_url}")
        print(f"CONNECT Key (decrypted): {connect_key}")
        
        # CMMS
        cmms_key = decrypt(profile.cmms_api_key_encrypted)
        print(f"CMMS URL: {profile.cmms_base_url}")
        print(f"CMMS Key (decrypted): {cmms_key}")
        
        # Test request to CMMS using the decrypted API key
        if profile.cmms_base_url and cmms_key:
            headers = {
                "Authorization": f"token {cmms_key}",
                "Content-Type": "application/json"
            }
            async with httpx.AsyncClient(timeout=10) as client:
                url = f"{profile.cmms_base_url}/api/method/frappe.auth.get_logged_user"
                try:
                    resp = await client.get(url, headers=headers)
                    print(f"CMMS request status: {resp.status_code}")
                    print(f"CMMS response body: {resp.text}")
                except Exception as e:
                    print(f"CMMS request failed: {e}")
                    
                # Test also with Bearer prefix
                headers_bearer = {
                    "Authorization": f"Bearer {cmms_key}",
                    "Content-Type": "application/json"
                }
                try:
                    resp = await client.get(url, headers=headers_bearer)
                    print(f"CMMS request (Bearer) status: {resp.status_code}")
                    print(f"CMMS response (Bearer) body: {resp.text}")
                except Exception as e:
                    print(f"CMMS request (Bearer) failed: {e}")
                    
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_conn())
