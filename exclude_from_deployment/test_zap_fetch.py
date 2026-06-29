import asyncio
import json
from app.database import SessionLocal
from app.models.company import CompanyProfile
from app.utils.encryption import decrypt
from app.adapters.zap import ZapAdapter

async def test_fetch():
    db = SessionLocal()
    try:
        profile = db.query(CompanyProfile).filter(CompanyProfile.id == 1).first()
        if not profile:
            print("No CompanyProfile with ID 1 found.")
            return

        api_key = decrypt(profile.zap_api_key_encrypted)
        print(f"Decrypted API Key prefix: {api_key[:8]}...")
        print(f"Base URL: {profile.zap_base_url}")
        print(f"Backend Company: {profile.zap_backend_company}")

        zap = ZapAdapter(
            base_url=profile.zap_base_url,
            api_key=api_key
        )

        print("\nTesting Connection...")
        connected = await zap.test_connection()
        print(f"Connection Status: {connected}")

        print("\nFetching products with company filter...")
        products = await zap.fetch_products(profile.zap_backend_company)
        print(f"Fetched {len(products)} products.")
        if products:
            print("First 5 products:")
            print(json.dumps(products[:5], indent=2))

        print("\nFetching products WITHOUT company filter (all products)...")
        all_products = await zap.fetch_products(None)
        print(f"Fetched {len(all_products)} products total.")
        if all_products:
            print("First 5 total products:")
            print(json.dumps(all_products[:5], indent=2))

    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_fetch())
