import asyncio
import json
from app.database import SessionLocal
from app.models.company import CompanyProfile
from app.utils.encryption import decrypt
from app.adapters.zap import ZapAdapter

async def test_complete_zap():
    db = SessionLocal()
    try:
        profile = db.query(CompanyProfile).filter(CompanyProfile.id == 1).first()
        if not profile:
            print("No CompanyProfile with ID 1 found.")
            return

        api_key = decrypt(profile.zap_api_key_encrypted)
        print("==================================================")
        print("⚡ STARTING COMPLETE LIVE ZAP CONNECTION DIAGNOSTICS")
        print("==================================================")
        print(f"Decrypted API Key prefix: {api_key[:8]}...")
        print(f"Base URL: {profile.zap_base_url}")
        print(f"Backend Company: {profile.zap_backend_company}")

        zap = ZapAdapter(
            base_url=profile.zap_base_url,
            api_key=api_key
        )

        print("\n--- 1. Testing Connection (frappe.auth.get_logged_user) ---")
        connected = await zap.test_connection()
        print(f"Result: {connected}")
        if not connected:
            print("Aborting remaining tests because connection test failed.")
            return

        print("\n--- 2. Fetching Company Mapping ---")
        company_data = await zap.fetch_company_mapping(profile.zap_backend_company)
        print(f"Result: {json.dumps(company_data, indent=2) if company_data else 'None'}")

        print("\n--- 3. Fetching Employee Details via Global Token ---")
        sample_user = "vinodkumarkolli@gmail.com"  # Common email in staging db
        emp = await zap.fetch_employee_by_email(sample_user, None)
        print(f"Employee Details: {json.dumps(emp, indent=2) if emp else 'None'}")

        print("\n--- 4. Fetching POS Profiles via Global Token ---")
        profiles = await zap.fetch_pos_profiles(sample_user, profile.zap_backend_company, None)
        print(f"POS Profiles: {json.dumps(profiles, indent=2)}")

        if profiles:
            first_profile_id = profiles[0]["name"]
            print(f"\n--- 5. Fetching POS Profile Detail for '{first_profile_id}' via Global Token ---")
            detail = await zap.fetch_pos_profile_detail(first_profile_id, None)
            print(f"POS Profile Detail: {json.dumps(detail, indent=2)}")

        print("\n--- 6. Fetching Customer beat/outlet mapping via Global Token ---")
        # Using a sample beat outlet ID
        mapping = await zap.fetch_customer_mapping("sample-outlet-id", None)
        print(f"Customer Mapping: {json.dumps(mapping, indent=2)}")

        print("\n--- 8. Fetching Products (Item Defaults) ---")
        products = await zap.fetch_products(profile.zap_backend_company)
        print(f"Fetched {len(products)} products with company filter.")

        all_products = await zap.fetch_products(None)
        print(f"Fetched {len(all_products)} products total.")

    except Exception as e:
        print(f"Error occurred during live diagnostics: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_complete_zap())
