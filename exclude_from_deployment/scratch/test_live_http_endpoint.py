import asyncio
import httpx

async def test_live_endpoint():
    print("==================================================")
    print("🌐 RUNNING LIVE END-TO-END HTTP ENDPOINT TEST")
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
        print(f"Cookies: {client.cookies}")
        
        if "user_id" not in resp.cookies and "session" not in resp.cookies:
            # Maybe the session cookie is set
            pass
            
        # 2. Call the test-connect endpoint
        print("\n2. Calling test-connect endpoint...")
        # Since it is a POST request, we can just call it
        resp_test = await client.post(f"{base_url}/company/profiles/1/test-connect")
        print(f"Endpoint HTTP Status: {resp_test.status_code}")
        print(f"Endpoint Response Body:")
        print(resp_test.text)

if __name__ == "__main__":
    asyncio.run(test_live_endpoint())
