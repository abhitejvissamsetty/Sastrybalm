import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.database import SessionLocal
from app.models.company import CompanyProfile
from app.utils.encryption import decrypt
from app.adapters.zap import ZapAdapter
import httpx
import json
import asyncio
import re
from decimal import Decimal
from datetime import date

def extract_gst_from_taxes(taxes: list) -> Decimal:
    """Extract effective GST rate from the item taxes child table.
    
    ERPNext Item.taxes rows have 'item_tax_template' like 'GST 12% - SE-K'
    and 'valid_from' date. We pick the most-recently-valid entry (valid_from <= today),
    then parse the % out of the template name.
    """
    if not taxes:
        return Decimal("0")
    
    today = date.today()
    
    # Filter to entries that are valid (valid_from <= today or no valid_from)
    valid_entries = []
    for t in taxes:
        vf = t.get("valid_from")
        if not vf:
            valid_entries.append((date.min, t))
        else:
            try:
                vf_date = date.fromisoformat(str(vf)[:10])
                if vf_date <= today:
                    valid_entries.append((vf_date, t))
            except ValueError:
                valid_entries.append((date.min, t))
    
    if not valid_entries:
        # All entries are future-dated; take the earliest one
        valid_entries = [(date.min, t) for t in taxes]
    
    # Sort by date descending, take the most recent
    valid_entries.sort(key=lambda x: x[0], reverse=True)
    _, best_entry = valid_entries[0]
    
    template = best_entry.get("item_tax_template", "")
    # Parse number before % sign: e.g. "GST 12% - SE-K" -> 12
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", template)
    if match:
        return Decimal(match.group(1))
    
    return Decimal("0")

async def main():
    db = SessionLocal()
    try:
        profile = db.query(CompanyProfile).filter(CompanyProfile.id == 1).first()
        api_key = decrypt(profile.zap_api_key_encrypted)
        zap = ZapAdapter(base_url=profile.zap_base_url, api_key=api_key)
        headers = zap.get_auth_headers("integration")
        
        async with httpx.AsyncClient(timeout=30) as client:
            # Fetch items without gst_rate
            params = {
                "fields": json.dumps(["name", "item_name", "item_code", "item_group", "standard_rate"]),
                "filters": json.dumps([
                    ["has_variants", "=", 0],
                    ["item_group", "=", "Products"],
                    ["disabled", "=", 0],
                    ["Item Default", "company", "=", profile.zap_backend_company]
                ]),
                "limit_page_length": 0,
            }
            resp = await client.get(f"{profile.zap_base_url}/api/resource/Item", headers=headers, params=params)
            print(f"List items status: {resp.status_code}")
            items = resp.json().get("data", [])
            print(f"Total items: {len(items)}")
            
            # For each item, fetch detail and extract GST
            for item in items[:5]:  # Test first 5 only
                item_code = item["name"]
                detail_resp = await client.get(
                    f"{profile.zap_base_url}/api/resource/Item/{item_code}",
                    headers=headers
                )
                if detail_resp.status_code == 200:
                    detail = detail_resp.json().get("data", {})
                    taxes = detail.get("taxes", [])
                    gst_rate = extract_gst_from_taxes(taxes)
                    print(f"  {item_code}: MRP={item.get('standard_rate')}, GST={gst_rate}% (taxes count: {len(taxes)})")
                else:
                    print(f"  {item_code}: Failed to fetch detail ({detail_resp.status_code})")
                    
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
