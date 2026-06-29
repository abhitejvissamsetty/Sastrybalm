import asyncio
import httpx

async def test_key():
    key = "9055da3de790c99:06bbf3526ebc8cb"
    urls = {
        "ZAP": "https://zap.staging.sravie.in",
        "CMMS": "https://cmms.staging.sravie.in",
        "CONNECT": "https://connect.staging.sravie.in"
    }
    
    headers = {
        "Authorization": f"token {key}",
        "Content-Type": "application/json"
    }
    
    print("==================================================")
    print("🔬 TESTING PROVIDED KEY ACROSS ALL THREE PORTALS")
    print("==================================================")
    
    async with httpx.AsyncClient(timeout=10) as client:
        for name, base_url in urls.items():
            url = f"{base_url}/api/method/frappe.auth.get_logged_user"
            try:
                resp = await client.get(url, headers=headers)
                print(f"[{name}] {url} -> Status: {resp.status_code}")
                print(f"[{name}] Response: {resp.text}")
            except Exception as e:
                print(f"[{name}] Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_key())
