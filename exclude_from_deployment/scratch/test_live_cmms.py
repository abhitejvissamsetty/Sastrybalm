import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app.models.company import CompanyProfile
from app.utils.encryption import decrypt
from app.adapters.cmms import CMSAdapter
import asyncio
import httpx
from datetime import datetime, timedelta

async def ensure_resources(client, base_url, headers):
    print("\nEnsuring prerequisite resources exist on CMMS Staging...")
    
    # 1. Ensure Location "Test Location"
    url_loc = f"{base_url}/api/resource/Location"
    loc_payload = {
        "location_name": "Test Location",
        "custom_location_type": "Retailer",
        "custom_beat_id": "Sample BEAT",
        "custom_address": "Sample Address",
        "custom_pincode": 600128,
        "latitude": 19.98734987,
        "longitude": 81.389470,
        "location": "{\"type\": \"FeatureCollection\", \"features\": [{\"type\": \"Feature\", \"properties\": {}, \"geometry\": {\"type\": \"Point\", \"coordinates\": [81.38947, 19.98734987]}}]}"
    }
    try:
        resp = await client.post(url_loc, headers=headers, json={"data": loc_payload})
        if resp.status_code == 200:
            print("- Created Location 'Test Location'")
        else:
            print(f"- Location 'Test Location' status: {resp.status_code} ({resp.text[:200]})")
    except Exception as e:
        print(f"- Location check error: {e}")
        
    # 2. Ensure Asset Category "Capital Equipment"
    url_cat = f"{base_url}/api/resource/Asset Category"
    cat_payload = {
        "asset_category_name": "Capital Equipment",
        "total_number_of_depreciations": 3,
        "frequency_of_depreciation": 12,
        "enable_cwip_accounting": 0,
        "accounts": [
            {
                "company_name": "Sravi Enterprises - Assets Kolapakkam",
                "fixed_asset_account": "Capital Equipment - SE-AK",
                "accumulated_depreciation_account": "Accumulated Depreciations - SE-AK",
                "depreciation_expense_account": "Depreciation - SE-AK"
            }
        ]
    }
    try:
        resp = await client.post(url_cat, headers=headers, json={"data": cat_payload})
        if resp.status_code == 200:
            print("- Created Asset Category 'Capital Equipment'")
        else:
            print(f"- Asset Category 'Capital Equipment' status: {resp.status_code} ({resp.text[:200]})")
    except Exception as e:
        print(f"- Asset Category check error: {e}")
        
    # 3. Ensure Service Item "Installation Service"
    url_item = f"{base_url}/api/resource/Item"
    svc_payload = {
        "item_code": "Installation Service",
        "item_name": "Installation Service",
        "item_group": "Consumable",
        "stock_uom": "Nos",
        "is_fixed_asset": 0,
        "is_stock_item": 0,
        "gst_hsn_code": "0101"
    }
    try:
        resp = await client.post(url_item, headers=headers, json={"data": svc_payload})
        if resp.status_code == 200:
            print("- Created Service Item 'Installation Service'")
        else:
            print(f"- Service Item 'Installation Service' status: {resp.status_code} ({resp.text[:200]})")
    except Exception as e:
        print(f"- Service Item check error: {e}")
        
    # 4. Ensure Item "MBLIT"
    mblit_payload = {
        "item_code": "MBLIT",
        "item_name": "Mounting Backlit",
        "item_group": "Consumable",
        "stock_uom": "Nos",
        "is_fixed_asset": 1,
        "is_stock_item": 0,
        "auto_create_assets": 1,
        "asset_category": "Capital Equipment",
        "asset_naming_series": "ACC-ASS-.YYYY.-",
        "gst_hsn_code": "0101"
    }
    try:
        resp = await client.post(url_item, headers=headers, json={"data": mblit_payload})
        if resp.status_code == 200:
            print("- Created Item 'MBLIT'")
        else:
            print(f"- Item 'MBLIT' status: {resp.status_code} ({resp.text[:200]})")
    except Exception as e:
        print(f"- Item 'MBLIT' check error: {e}")

async def test_live_cmms():
    print("CMMS Dynamic Integration Verification Script")
    print("--------------------------------------------")
    
    db = SessionLocal()
    try:
        profile = db.query(CompanyProfile).filter(CompanyProfile.id == 1).first()
        if not profile:
            print("ERROR: Company profile ZTE (ID 1) not found in local database.")
            return
        
        cmms_key = decrypt(profile.cmms_api_key_encrypted)
        print(f"Loaded Profile: {profile.name} ({profile.code})")
        print(f"Staging Base URL: {profile.cmms_base_url}")
        print(f"Decrypted Key: {cmms_key}")
        
        headers = {
            "Authorization": f"token {cmms_key}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=15) as client:
            await ensure_resources(client, profile.cmms_base_url, headers)
            
        # Instantiate dynamic CMSAdapter
        adapter = CMSAdapter(
            base_url=profile.cmms_base_url,
            api_key=cmms_key
        )
        
        print("\n--- 1. Testing Connection ---")
        conn_ok = await adapter.test_connection()
        print(f"Connection Status: {'SUCCESS' if conn_ok else 'FAILED'}")
        if not conn_ok:
            print("Aborting live tests because connection failed.")
            return
            
        print("\n--- 2. Creating and Submitting Material Request ---")
        schedule_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        mr_payload = {
            "material_request_type": "Purchase",
            "company": "Sravi Enterprises - Assets Kolapakkam",
            "custom_location": "Test Location",
            "custom_raised_by": "vinodkumarkolli@gmail.com",
            "items": [
                {
                    "item_code": "MBLIT",
                    "qty": 1,
                    "custom_request_description": "Auto-generated test material request from Safar",
                    "schedule_date": schedule_date,
                    "warehouse": "Stores - SE-AK",
                    "uom": "Nos",
                    "expense_account": "Capital Equipment - SE-AK",
                    "cost_center": "Main - SE-AK"
                }
            ]
        }
        
        try:
            print("Sending Material Request POST...")
            mr_result = await adapter.create_material_request(mr_payload)
            print("SUCCESS! Material Request created and submitted successfully.")
            print(f"Submitted MR Name: {mr_result.get('name')}")
            print(f"Docstatus: {mr_result.get('docstatus')}")
            
            # Fetch MR status details
            print(f"Fetching status for MR '{mr_result.get('name')}'...")
            status_res = await adapter.get_work_order_status(mr_result.get('name'))
            print(f"Doc status returned: {status_res.get('data', {}).get('status') or status_res.get('status')}")
        except Exception as e:
            print(f"MR Creation Failed: {e}")
            
        print("\n--- 3. Creating and Submitting Asset Capitalization ---")
        posting_date = datetime.now().strftime("%Y-%m-%d")
        ac_payload = {
            "company": "Sravi Enterprises - Assets Kolapakkam",
            "target_item_code": "MBLIT",
            "target_asset_location": "Test Location",
            "posting_date": posting_date,
            "service_items": [
                {
                    "item_code": "Installation Service",
                    "qty": 1,
                    "uom": "Nos",
                    "rate": 100.0,
                    "expense_account": "Capital Equipment - SE-AK",
                    "cost_center": "Main - SE-AK"
                }
            ],
            "custom_installation_notes": "Auto-generated test asset capitalization from Safar",
            "custom_installation_photo_1": "",
            "custom_installation_length": 8,
            "custom_installation_height": 5,
            "custom_installation_depth": 0.8
        }
        
        try:
            print("Sending Asset Capitalization POST...")
            ac_result = await adapter.create_asset_capitalization(ac_payload)
            print("SUCCESS! Asset Capitalization created and submitted successfully.")
            print(f"Submitted AC Name: {ac_result.get('name')}")
            print(f"Docstatus: {ac_result.get('docstatus')}")
        except Exception as e:
            print(f"AC Creation Failed: {e}")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_live_cmms())
