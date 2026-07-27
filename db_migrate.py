import os
from sqlalchemy import text
from app.database import engine
from app.models.base import Base

# Ensure all models are imported so Base.metadata is fully populated
from app.models import *

def add_column_safely(conn, table, column, definition):
    try:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
        print(f"Added column {column} to {table}")
    except Exception as e:
        err_str = str(e).lower()
        if "1060" in err_str or "duplicate column" in err_str or "already exists" in err_str:
            # Already exists, ignore cleanly
            pass
        else:
            print(f"Error adding {column} to {table}: {e}")

def run_migrations():
    print("Running database migrations...")
    
    # 1. Ensure all tables defined in models exist
    print("Ensuring all database tables exist...")
    Base.metadata.create_all(bind=engine)
    
    with engine.begin() as conn:
        # 2. Update existing tables with alter statements
        
        # Outlets
        if conn.engine.name != "sqlite":
            try:
                # First change the enum type or use VARCHAR
                conn.execute(text("ALTER TABLE outlets MODIFY COLUMN status VARCHAR(50) DEFAULT 'active'"))
                conn.execute(text("UPDATE outlets SET status = 'active' WHERE status = 'approved'"))
                conn.execute(text("UPDATE outlets SET status = 'inactive' WHERE status IN ('draft', 'rejected')"))
            except Exception:
                pass
            
        add_column_safely(conn, "outlets", "gstin", "VARCHAR(15) NULL")
        add_column_safely(conn, "outlets", "pincode", "VARCHAR(6) NULL")
        add_column_safely(conn, "outlets", "shop_type", "VARCHAR(50) NULL")
        add_column_safely(conn, "outlets", "external_id", "VARCHAR(100) NULL")
        add_column_safely(conn, "outlets", "channel", "VARCHAR(50) NULL")
        add_column_safely(conn, "outlets", "photo_url", "TEXT NULL")
        add_column_safely(conn, "outlets", "is_active", "BOOLEAN NOT NULL DEFAULT 1")
        add_column_safely(conn, "outlet_versions", "photo_url", "TEXT NULL")
        add_column_safely(conn, "material_requests", "image_url", "TEXT NULL")
        add_column_safely(conn, "asset_capitalizations", "image_url", "TEXT NULL")
        add_column_safely(conn, "vendor_quotations", "invoice_photo_url", "TEXT NULL")
        add_column_safely(conn, "alerts", "user_id", "INT NULL")
        add_column_safely(conn, "alerts", "geography_id", "INT NULL")
        add_column_safely(conn, "alerts", "vendor_id", "INT NULL")
        add_column_safely(conn, "orders", "order_type", "VARCHAR(20) NOT NULL DEFAULT 'Secondary'")
            
        # Users
        try:
            # Drop foreign keys if they exist
            try:
                conn.execute(text("ALTER TABLE users DROP FOREIGN KEY fk_user_position"))
            except Exception: pass
            try:
                conn.execute(text("ALTER TABLE users DROP FOREIGN KEY fk_user_zone"))
            except Exception: pass
            
            # Drop old columns
            try:
                conn.execute(text("ALTER TABLE users DROP COLUMN position_id"))
            except Exception: pass
            try:
                conn.execute(text("ALTER TABLE users DROP COLUMN zone_id"))
            except Exception: pass
        except Exception as e:
            print(f"Users pre-migration error: {e}")
            
        if conn.engine.name != "sqlite":
            try:
                conn.execute(text("ALTER TABLE users MODIFY COLUMN role VARCHAR(50) NOT NULL DEFAULT 'field_rep'"))
            except Exception as e:
                print(f"Error modifying users.role column: {e}")
            
        add_column_safely(conn, "users", "employee_id", "VARCHAR(100) NULL")
        add_column_safely(conn, "users", "phone", "VARCHAR(20) NULL")
        add_column_safely(conn, "users", "imei", "VARCHAR(50) NULL")
        add_column_safely(conn, "users", "payment_mode", "VARCHAR(50) NULL")
        add_column_safely(conn, "users", "denomination_mandatory", "BOOLEAN NOT NULL DEFAULT 0")
        add_column_safely(conn, "users", "geography_id", "INT NULL")
        add_column_safely(conn, "users", "vendor_id", "INT NULL")
        add_column_safely(conn, "users", "is_active", "BOOLEAN NOT NULL DEFAULT 1")
            
        # Orders
        add_column_safely(conn, "orders", "payment_settlement", "VARCHAR(50) NOT NULL DEFAULT 'unpaid'")
        add_column_safely(conn, "orders", "connect_ref", "VARCHAR(100) NULL")
        add_column_safely(conn, "orders", "channel_partner_id", "INT NULL")
            
        # Order Items
        add_column_safely(conn, "order_items", "gst_rate", "DECIMAL(5, 2) NOT NULL DEFAULT 0")
        add_column_safely(conn, "order_items", "discount_pct", "DECIMAL(5, 2) NOT NULL DEFAULT 0")
            
        # Payments
        add_column_safely(conn, "payments", "payment_type", "VARCHAR(50) NOT NULL DEFAULT 'invoice_payment'")
        add_column_safely(conn, "payments", "denom_2000", "INT NOT NULL DEFAULT 0")
        add_column_safely(conn, "payments", "submission_id", "INT NULL")
        try:
            conn.execute(text("ALTER TABLE payments ADD CONSTRAINT fk_payment_submission FOREIGN KEY (submission_id) REFERENCES payment_submissions(id) ON DELETE SET NULL"))
        except Exception: pass

        # Beats
        add_column_safely(conn, "beats", "beat_type", "VARCHAR(50) NOT NULL DEFAULT 'GT'")
        add_column_safely(conn, "beats", "beat_grade", "VARCHAR(50) NULL")
        add_column_safely(conn, "beats", "description", "TEXT NULL")
        add_column_safely(conn, "beats", "pincodes", "VARCHAR(500) NULL")
        add_column_safely(conn, "beats", "erp_id", "VARCHAR(100) NULL")
        add_column_safely(conn, "beats", "is_active", "BOOLEAN NOT NULL DEFAULT 1")
        
        # Local Channel Partners
        add_column_safely(conn, "local_channel_partners", "beat_type", "VARCHAR(50) NOT NULL DEFAULT 'GT'")
        add_column_safely(conn, "local_channel_partners", "partner_type", "VARCHAR(100) NULL DEFAULT 'Distributor'")
        add_column_safely(conn, "local_channel_partners", "sales_channels", "TEXT NULL")
        add_column_safely(conn, "local_channel_partners", "geography_id", "INT NULL")
        add_column_safely(conn, "local_channel_partners", "contact_person", "VARCHAR(255) NULL")
        add_column_safely(conn, "local_channel_partners", "mobile", "VARCHAR(20) NULL")
        add_column_safely(conn, "local_channel_partners", "address", "TEXT NULL")
        add_column_safely(conn, "local_channel_partners", "erp_id", "VARCHAR(100) NULL")
        add_column_safely(conn, "local_channel_partners", "notification_preference", "VARCHAR(50) NOT NULL DEFAULT 'none'")
        add_column_safely(conn, "local_channel_partners", "notification_channel", "VARCHAR(50) NOT NULL DEFAULT 'email'")

        # Products
        add_column_safely(conn, "products", "unit_cost", "DECIMAL(10, 2) NOT NULL DEFAULT 0")
        add_column_safely(conn, "products", "stock_qty", "INT NOT NULL DEFAULT 0")
        add_column_safely(conn, "products", "reorder_level", "INT NOT NULL DEFAULT 10")
        add_column_safely(conn, "products", "category_type", "VARCHAR(50) NOT NULL DEFAULT 'Sales'")
        add_column_safely(conn, "products", "warehouse_id", "INT NULL")
        add_column_safely(conn, "products", "warehouse_location", "VARCHAR(100) NULL")
        add_column_safely(conn, "products", "is_stockable", "BOOLEAN NOT NULL DEFAULT 1")

        # Stock Movements
        add_column_safely(conn, "stock_movements", "warehouse_id", "INT NULL")

        # Warehouses
        add_column_safely(conn, "warehouses", "geography_id", "INT NULL")

        # Positions
        add_column_safely(conn, "positions", "warehouse_id", "INT NULL")

        # System Configuration - Default row
        conn.execute(text("INSERT IGNORE INTO system_configuration (id) VALUES (1)"))

        # Material Requests & Vendors
        add_column_safely(conn, "material_requests", "vendor_id", "INT NULL")

        # Work Orders
        add_column_safely(conn, "work_orders", "material_request_id", "INT NULL")
        add_column_safely(conn, "work_orders", "vendor_id", "INT NULL")
        add_column_safely(conn, "work_orders", "qc_photo_url", "TEXT NULL")
        add_column_safely(conn, "work_orders", "qc_notes", "TEXT NULL")
        add_column_safely(conn, "work_orders", "qc_verified_at", "DATETIME NULL")
        add_column_safely(conn, "work_orders", "qc_verified_by_id", "INT NULL")
        add_column_safely(conn, "system_configuration", "smtp_host", "VARCHAR(255) NULL")
        add_column_safely(conn, "system_configuration", "smtp_port", "INT NOT NULL DEFAULT 587")
        add_column_safely(conn, "system_configuration", "smtp_user", "VARCHAR(255) NULL")
        add_column_safely(conn, "system_configuration", "smtp_password", "TEXT NULL")
        add_column_safely(conn, "system_configuration", "auto_approval_cutoff_hours", "INT NOT NULL DEFAULT 24")
        add_column_safely(conn, "system_configuration", "s3_endpoint_url", "VARCHAR(255) NULL")
        add_column_safely(conn, "system_configuration", "s3_bucket_name", "VARCHAR(255) NULL")
        add_column_safely(conn, "system_configuration", "s3_access_key_id", "VARCHAR(255) NULL")
        add_column_safely(conn, "system_configuration", "s3_secret_access_key", "TEXT NULL")
        add_column_safely(conn, "system_configuration", "s3_region_name", "VARCHAR(100) NULL DEFAULT 'us-west-004'")
        add_column_safely(conn, "system_configuration", "s3_is_enabled", "BOOLEAN NOT NULL DEFAULT 0")
        add_column_safely(conn, "system_configuration", "s3_public_url_prefix", "VARCHAR(255) NULL")

        # Files Bucket Separate S3 Settings
        add_column_safely(conn, "system_configuration", "s3_files_is_enabled", "BOOLEAN NOT NULL DEFAULT 0")
        add_column_safely(conn, "system_configuration", "s3_files_endpoint_url", "VARCHAR(255) NULL")
        add_column_safely(conn, "system_configuration", "s3_files_bucket_name", "VARCHAR(255) NULL")
        add_column_safely(conn, "system_configuration", "s3_files_access_key_id", "VARCHAR(255) NULL")
        add_column_safely(conn, "system_configuration", "s3_files_secret_access_key", "TEXT NULL")
        add_column_safely(conn, "system_configuration", "s3_files_region_name", "VARCHAR(100) NULL DEFAULT 'us-west-004'")
        add_column_safely(conn, "system_configuration", "s3_files_public_url_prefix", "VARCHAR(255) NULL")
        add_column_safely(conn, "system_configuration", "whatsapp_api_key", "TEXT NULL")
        add_column_safely(conn, "system_configuration", "whatsapp_phone_number_id", "VARCHAR(255) NULL")
        add_column_safely(conn, "system_configuration", "whatsapp_business_account_id", "VARCHAR(255) NULL")
        add_column_safely(conn, "system_configuration", "whatsapp_is_enabled", "BOOLEAN NOT NULL DEFAULT 0")
        add_column_safely(conn, "system_configuration", "smtp_from", "VARCHAR(255) NULL")
        add_column_safely(conn, "system_configuration", "smtp_use_tls", "BOOLEAN NOT NULL DEFAULT 1")

        # Visit Records - Joint Working
        add_column_safely(conn, "visit_records", "is_joint_visit", "BOOLEAN NOT NULL DEFAULT 0")
        add_column_safely(conn, "visit_records", "joint_with_user_id", "INT NULL")
        add_column_safely(conn, "visit_records", "joint_with_name", "VARCHAR(255) NULL")
        add_column_safely(conn, "visit_records", "joint_with_role", "VARCHAR(100) NULL")
        add_column_safely(conn, "visit_records", "joint_notes", "TEXT NULL")
            
        # Positions
        add_column_safely(conn, "positions", "level", "VARCHAR(50) NOT NULL DEFAULT 'L1'")
        add_column_safely(conn, "positions", "reporting_to_id", "INT NULL")
        add_column_safely(conn, "positions", "is_active", "BOOLEAN NOT NULL DEFAULT 1")
        try:
            conn.execute(text("ALTER TABLE positions ADD CONSTRAINT fk_position_reporting FOREIGN KEY (reporting_to_id) REFERENCES positions(id) ON DELETE SET NULL"))
        except Exception: pass
            
        # Company Profiles
        add_column_safely(conn, "company_profiles", "zap_base_url", "VARCHAR(500) NULL")
        add_column_safely(conn, "company_profiles", "zap_api_key_encrypted", "TEXT NULL")
        add_column_safely(conn, "company_profiles", "zap_backend_company", "VARCHAR(255) NULL")
        add_column_safely(conn, "company_profiles", "cmms_base_url", "VARCHAR(500) NULL")
        add_column_safely(conn, "company_profiles", "cmms_api_key_encrypted", "TEXT NULL")
        add_column_safely(conn, "company_profiles", "cmms_backend_company", "VARCHAR(255) NULL")
        add_column_safely(conn, "company_profiles", "connect_base_url", "VARCHAR(500) NULL")
        add_column_safely(conn, "company_profiles", "connect_api_key_encrypted", "TEXT NULL")
        add_column_safely(conn, "company_profiles", "connect_backend_company", "VARCHAR(255) NULL")
        add_column_safely(conn, "company_profiles", "tags", "TEXT NULL")
        add_column_safely(conn, "company_profiles", "is_active", "BOOLEAN NOT NULL DEFAULT 1")

        # Products & Geographies
        add_column_safely(conn, "products", "is_active", "BOOLEAN NOT NULL DEFAULT 1")
        add_column_safely(conn, "products", "company_profile_id", "INT NULL")
        try:
            conn.execute(text("ALTER TABLE products ADD CONSTRAINT fk_product_company FOREIGN KEY (company_profile_id) REFERENCES company_profiles(id) ON DELETE SET NULL"))
        except Exception: pass
        add_column_safely(conn, "geographies", "is_active", "BOOLEAN NOT NULL DEFAULT 1")

        # Product Alias Maps
        add_column_safely(conn, "product_alias_maps", "conversion_factor", "DECIMAL(10, 5) NOT NULL DEFAULT 1.0")
            
        # System Configuration - Cleanup obsolete columns
        try: conn.execute(text("ALTER TABLE system_configuration DROP COLUMN zap_fetch_interval_minutes"))
        except Exception: pass
        try: conn.execute(text("ALTER TABLE system_configuration DROP COLUMN cmms_post_interval_minutes"))
        except Exception: pass
        try: conn.execute(text("ALTER TABLE system_configuration DROP COLUMN connect_sync_interval_minutes"))
        except Exception: pass
        add_column_safely(conn, "system_configuration", "flag_gps_distance_metres", "INT NOT NULL DEFAULT 100")
        add_column_safely(conn, "system_configuration", "flag_min_visit_seconds", "INT NOT NULL DEFAULT 120")
        add_column_safely(conn, "system_configuration", "payment_mode", "VARCHAR(50) NULL DEFAULT 'cash_only'")
        add_column_safely(conn, "system_configuration", "denomination_mandatory", "BOOLEAN NOT NULL DEFAULT 0")
        
        # Users - Activation and registration fields
        add_column_safely(conn, "users", "activation_code", "VARCHAR(10) NULL")
        add_column_safely(conn, "users", "is_registered", "BOOLEAN NOT NULL DEFAULT 0")

        # Timesheets
        add_column_safely(conn, "timesheets", "attendance_id", "INT NULL")
        add_column_safely(conn, "timesheets", "approval_status", "VARCHAR(50) NOT NULL DEFAULT 'pending'")
        add_column_safely(conn, "timesheets", "approved_by_id", "INT NULL")
        add_column_safely(conn, "timesheets", "approved_at", "DATETIME NULL")
        add_column_safely(conn, "timesheets", "rejection_reason", "TEXT NULL")
        add_column_safely(conn, "timesheets", "activity_type", "VARCHAR(100) NULL")
        try:
            conn.execute(text("ALTER TABLE timesheets ADD CONSTRAINT fk_timesheet_attendance FOREIGN KEY (attendance_id) REFERENCES attendance(id) ON DELETE SET NULL"))
        except Exception: pass
        try:
            conn.execute(text("ALTER TABLE timesheets ADD CONSTRAINT fk_timesheet_approved_by FOREIGN KEY (approved_by_id) REFERENCES users(id) ON DELETE SET NULL"))
        except Exception: pass

        # Archival & Retention Columns for Parquet Hybrid Lifecycle
        add_column_safely(conn, "system_configuration", "archival_retention_days", "INT NOT NULL DEFAULT 90")
        
        archival_tables = [
            "orders", "order_items", "payments", "attendance", "timesheets",
            "expenses", "material_requests", "material_request_history_logs",
            "vendor_quotations", "work_orders", "stock_movements"
        ]
        for tbl in archival_tables:
            add_column_safely(conn, tbl, "is_archived", "BOOLEAN NOT NULL DEFAULT 0")
            add_column_safely(conn, tbl, "archived_at", "DATETIME NULL")

        # Warehouses
        add_column_safely(conn, "warehouses", "contact_person", "VARCHAR(255) NULL")
        add_column_safely(conn, "warehouses", "mobile", "VARCHAR(20) NULL")

        # Vendors
        add_column_safely(conn, "vendors", "geography_id", "INT NULL")

    print("Updates applied. Now running create_all to create missing tables...")
    # This will create any tables that don't exist yet (attendance, vendors, beat_types_master, etc.)
    Base.metadata.create_all(bind=engine)

    # Seed default Beat Types Master
    try:
        from app.utils.beat_types import seed_default_beat_types
        from app.database import SessionLocal
        db_session = SessionLocal()
        seed_default_beat_types(db_session)
        db_session.close()
        print("Beat Types Master seeded successfully!")
    except Exception as e:
        print(f"Seeding error: {e}")

    print("Database migrations completed successfully!")

if __name__ == "__main__":
    run_migrations()
