import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app.models.product import Product
from app.models.product_mapping import ProductAliasMap
from app.models.company import CompanyProfile

db = SessionLocal()
try:
    print("PRODUCTS:")
    products = db.query(Product).all()
    for p in products:
        print(f"- ID: {p.id}, Name: {p.name}, SKU: {p.sku}, ERP ID: {p.erp_id}")
        
    print("\nPRODUCT ALIAS MAPS:")
    aliases = db.query(ProductAliasMap).all()
    for a in aliases:
        print(f"- ID: {a.id}, Company Profile ID: {a.company_profile_id}, Product ID: {a.product_id}, CMMS Item Code: {a.cmms_item_code}, Connect Item Code: {a.connect_item_code}")
        
    print("\nCOMPANY PROFILES:")
    companies = db.query(CompanyProfile).all()
    for c in companies:
        print(f"- ID: {c.id}, Name: {c.name}, Tags: {c.get_tags()}")
finally:
    db.close()
