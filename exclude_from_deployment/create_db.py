#!/usr/bin/env python3
"""
Run this script once to create the database, tables, and seed the admin user.
Safe to re-run — it skips existing data and applies missing columns.

    python create_db.py
"""
import pymysql
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal, engine
from app.models import (  # noqa: registers all models with Base
    geography, company, position, beat, outlet, product, user as user_models,
    order, payment, expense, timesheet, material_request, alert,
)
from app.models.base import Base
from app.models.company import PaymentMode, SystemConfiguration
from app.models.user import User, UserRole
from app.utils.security import hash_password


def create_database() -> None:
    conn = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        charset="utf8mb4",
    )
    with conn.cursor() as cur:
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{settings.db_name}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    conn.close()
    print(f"[ok] Database `{settings.db_name}` ready.")


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    print("[ok] Tables created / verified.")


def apply_schema_updates() -> None:
    """Add Phase 2 FK columns to users table if they don't exist yet."""
    columns_to_add = [
        ("position_id", "INT NULL, ADD CONSTRAINT fk_user_position FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE SET NULL"),
        ("zone_id", "INT NULL, ADD CONSTRAINT fk_user_zone FOREIGN KEY (zone_id) REFERENCES geographies(id) ON DELETE SET NULL"),
        ("company_profile_id", "INT NULL, ADD CONSTRAINT fk_user_company FOREIGN KEY (company_profile_id) REFERENCES company_profiles(id) ON DELETE SET NULL"),
    ]
    with engine.connect() as conn:
        for col, definition in columns_to_add:
            result = conn.execute(text(
                f"SELECT COUNT(*) FROM information_schema.columns "
                f"WHERE table_schema = :db AND table_name = 'users' AND column_name = :col"
            ), {"db": settings.db_name, "col": col})
            if result.scalar() == 0:
                try:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {definition}"))
                    conn.commit()
                    print(f"[ok] Added column users.{col}")
                except Exception as e:
                    print(f"[warn] Could not add users.{col}: {e}")
            else:
                print(f"[skip] Column users.{col} already exists.")


def seed_admin() -> None:
    db = SessionLocal()
    try:
        if db.query(User).filter(User.role == UserRole.admin).first():
            print("[skip] Admin user already exists.")
        else:
            admin = User(
                email="admin@safar.com",
                username="admin",
                full_name="System Administrator",
                hashed_password=hash_password("Admin@123"),
                role=UserRole.admin,
                is_active=True,
            )
            db.add(admin)
            db.commit()
            print("[ok] Default admin user created:")
            print("      Username : admin")
            print("      Password : Admin@123")
            print("      IMPORTANT: change this password after first login!")
    finally:
        db.close()


def seed_system_config() -> None:
    db = SessionLocal()
    try:
        if db.query(SystemConfiguration).filter(SystemConfiguration.id == 1).first():
            print("[skip] System configuration already exists.")
        else:
            db.add(SystemConfiguration(
                id=1,
                payment_mode=PaymentMode.cash_and_online,
                denomination_mandatory=False,
                gps_threshold_metres=100,
                sync_interval_seconds=300,
            ))
            db.commit()
            print("[ok] Default system configuration seeded.")
    finally:
        db.close()


def seed_products() -> None:
    from decimal import Decimal
    from app.models.product import Product
    db = SessionLocal()
    try:
        if db.query(Product).count() > 0:
            print("[skip] Products already seeded.")
        else:
            products = [
                Product(
                    name="Safar Regular",
                    erp_id="PROD-BALM-REG",
                    sku="SB-REG-25G",
                    division="OTC",
                    primary_category="Balms",
                    secondary_category="Pain Relief",
                    mrp=Decimal("50.00"),
                    gst_rate=Decimal("18.00"),
                    must_sell=True,
                    is_active=True
                ),
                Product(
                    name="Safar Extra Strong",
                    erp_id="PROD-BALM-EXT",
                    sku="SB-EXT-25G",
                    division="OTC",
                    primary_category="Balms",
                    secondary_category="Pain Relief",
                    mrp=Decimal("65.00"),
                    gst_rate=Decimal("18.00"),
                    must_sell=True,
                    is_active=True
                ),
                Product(
                    name="Safar Pain Relief Spray",
                    erp_id="PROD-SPRAY-PR",
                    sku="SB-SPRAY-50ML",
                    division="OTC",
                    primary_category="Sprays",
                    secondary_category="Pain Relief",
                    mrp=Decimal("120.00"),
                    gst_rate=Decimal("18.00"),
                    must_sell=False,
                    is_active=True
                ),
                Product(
                    name="Safar Inhaler",
                    erp_id="PROD-INH-01",
                    sku="SB-INH-2ML",
                    division="OTC",
                    primary_category="Inhalers",
                    secondary_category="Cold Relief",
                    mrp=Decimal("30.00"),
                    gst_rate=Decimal("12.00"),
                    must_sell=False,
                    is_active=True
                ),
                Product(
                    name="Safar Herbal Ointment",
                    erp_id="PROD-OINT-HB",
                    sku="SB-OINT-30G",
                    division="OTC",
                    primary_category="Ointments",
                    secondary_category="Skin Care",
                    mrp=Decimal("85.00"),
                    gst_rate=Decimal("18.00"),
                    must_sell=False,
                    is_active=True
                )
            ]
            for p in products:
                db.add(p)
            db.commit()
            print(f"[ok] Seeded {len(products)} default products.")
    finally:
        db.close()


if __name__ == "__main__":
    print("=== Safar DB Setup ===")
    create_database()
    create_tables()
    apply_schema_updates()
    seed_admin()
    seed_system_config()
    seed_products()
    print("=== Done. Run: python run.py ===")
