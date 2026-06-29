import asyncio
import httpx

async def test_render():
    print("==================================================")
    print("🌐 TESTING PROFILE EDIT FORM RENDERING")
    print("==================================================")
    
    base_url = "http://127.0.0.1:8001"
    
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        # 1. Login as Admin
        print("\n1. Logging in as Admin...")
        login_data = {
            "username": "admin",
            "password": "Admin@123"
        }
        resp = await client.post(f"{base_url}/login", data=login_data)
        print(f"Login Response: {resp.status_code}")
        
        # 2. Get the Edit page for profile 1
        print("\n2. Fetching profile edit page...")
        resp_edit = await client.get(f"{base_url}/company/profiles/1/edit")
        print(f"Edit page HTTP Status: {resp_edit.status_code}")
        
        if resp_edit.status_code == 200:
            print("✅ Success! Page rendered successfully.")
            # Check if our new "Connected" badges exist in the HTML
            html = resp_edit.text
            if "Connected" in html:
                print("✅ Found 'Connected' indicator badge in HTML!")
            else:
                print("❌ 'Connected' indicator badge not found in HTML.")
        else:
            print(f"❌ Failed to render page. Content: {resp_edit.text[:500]}")

if __name__ == "__main__":
    asyncio.run(test_render())
