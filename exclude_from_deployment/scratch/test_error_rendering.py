import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.database import SessionLocal
from app.models.company import CompanyProfile
import httpx

async def test_error_render():
    print("==================================================")
    print("🔬 TESTING ERROR BANNERS AND BADGES RENDERING")
    print("==================================================")
    
    db = SessionLocal()
    original_tags = []
    try:
        profile = db.query(CompanyProfile).filter(CompanyProfile.id == 1).first()
        if not profile:
            print("❌ Profile not found!")
            return
            
        original_tags = profile.get_tags()
        print(f"Original tags: {original_tags}")
        
        # 1. Set CMMS-ERROR tag
        temp_tags = original_tags.copy()
        if "CMMS-READY" in temp_tags:
            temp_tags.remove("CMMS-READY")
        if "CMMS-ERROR" not in temp_tags:
            temp_tags.append("CMMS-ERROR")
        profile.set_tags(temp_tags)
        db.commit()
        print("✅ Set CMMS-ERROR tag in database.")
        
        # 2. Fetch the Edit Form over HTTP
        base_url = "http://127.0.0.1:8001"
        async with httpx.AsyncClient(timeout=20) as client:
            # Login
            await client.post(f"{base_url}/login", data={"username": "admin", "password": "Admin@123"})
            
            # Get form
            resp = await client.get(f"{base_url}/company/profiles/1/edit")
            html = resp.text
            
            # Verify Indicators
            print("\nChecking HTML content for CMMS error indicators:")
            if "Connection Failed" in html:
                print("  ✅ Found 'Connection Failed' badge!")
            else:
                print("  ❌ 'Connection Failed' badge NOT found.")
                
            if "Credentials not working.</span> The last connection attempt to the CMMS backend failed" in html:
                print("  ✅ Found CMMS warning banner!")
            else:
                print("  ❌ CMMS warning banner NOT found.")
                
    except Exception as e:
        print(f"❌ Error during test: {e}")
    finally:
        # Restore original tags
        profile = db.query(CompanyProfile).filter(CompanyProfile.id == 1).first()
        if profile:
            profile.set_tags(original_tags)
            db.commit()
            print("\n✅ Restored original tags in database.")
        db.close()

if __name__ == "__main__":
    asyncio.run(test_error_render())
