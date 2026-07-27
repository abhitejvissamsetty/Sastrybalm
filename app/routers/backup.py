import os
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_roles
from app.models.user import User, UserRole
from app.models.company import SystemConfiguration
from app.utils.backup_service import (BACKUP_DIR, create_full_system_backup,
                                      list_existing_backups)
from app.utils.flash import get_flash, set_flash_error, set_flash_success

router = APIRouter(prefix="/settings/backup", tags=["backup"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def backup_dashboard(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    from app.utils.s3_service import get_s3_config, test_s3_connection
    s3_config = get_s3_config(db)
    s3_is_enabled = bool(s3_config.get("s3_is_enabled"))
    s3_working = False
    s3_error_msg = ""
    if s3_is_enabled:
        s3_working, s3_error_msg = test_s3_connection(s3_config, bucket_type="permanent")
    else:
        s3_error_msg = "Permanent S3 Bucket is disabled in S3 Settings."

    sys_config = db.query(SystemConfiguration).filter(SystemConfiguration.id == 1).first()
    if not sys_config:
        sys_config = SystemConfiguration(id=1, archival_retention_days=90)
        db.add(sys_config)
        db.commit()

    # Compute live archival statistics
    from app.models.order import Order
    from app.models.payment import Payment
    from app.models.attendance import Attendance
    from app.models.timesheet import Timesheet
    from app.models.expense import Expense
    from app.models.material_request import MaterialRequest
    from app.models.inventory import StockMovement

    archival_models = [Order, Payment, Attendance, Timesheet, Expense, MaterialRequest, StockMovement]
    active_hot_count = sum(db.query(m).filter(m.is_archived == False).count() for m in archival_models)
    soft_archived_count = sum(db.query(m).filter(m.is_archived == True).count() for m in archival_models)

    backups = list_existing_backups()
    return templates.TemplateResponse("settings/backup.html", {
        "request": request,
        "current_user": current_user,
        "backups": backups,
        "s3_is_enabled": s3_is_enabled,
        "s3_working": s3_working,
        "s3_error_msg": s3_error_msg,
        "retention_days": sys_config.archival_retention_days or 90,
        "active_hot_count": active_hot_count,
        "soft_archived_count": soft_archived_count,
        **get_flash(request),
    })


@router.post("/retention")
async def update_retention_settings(
    request: Request,
    archival_retention_days: int = Form(90),
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    sys_config = db.query(SystemConfiguration).filter(SystemConfiguration.id == 1).first()
    if not sys_config:
        sys_config = SystemConfiguration(id=1)
        db.add(sys_config)
    
    retention = max(7, min(3650, archival_retention_days))
    sys_config.archival_retention_days = retention
    db.commit()

    set_flash_success(request, f"Archival hard purge retention window updated to {retention} days.")
    return RedirectResponse("/settings/backup", status_code=302)


@router.post("/create")
async def backup_create(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
):
    try:
        filepath = create_full_system_backup()
        filename = os.path.basename(filepath)
        set_flash_success(request, f"System backup '{filename}' generated successfully.")
    except Exception as e:
        set_flash_error(request, f"Backup creation failed: {str(e)}")
    return RedirectResponse("/settings/backup", status_code=302)


@router.get("/download/{filename}")
async def backup_download(
    filename: str,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
):
    filepath = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(filepath) or not (filename.endswith(".sql") or filename.endswith(".zip")):
        return RedirectResponse("/settings/backup", status_code=302)
    
    media_type = "application/sql" if filename.endswith(".sql") else "application/zip"
    return FileResponse(
        path=filepath,
        filename=filename,
        media_type=media_type
    )


@router.post("/delete/{filename}")
async def backup_delete(
    filename: str,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
):
    filepath = os.path.join(BACKUP_DIR, filename)
    if os.path.exists(filepath) and (filename.endswith(".sql") or filename.endswith(".zip")):
        os.remove(filepath)
        set_flash_success(request, f"Backup '{filename}' deleted.")
    else:
        set_flash_error(request, "Backup file not found.")
    return RedirectResponse("/settings/backup", status_code=302)


@router.post("/parquet-rolling-backup")
async def backup_parquet_rolling(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    from app.utils.s3_service import get_s3_config, test_s3_connection
    s3_config = get_s3_config(db)
    if not s3_config.get("s3_is_enabled"):
        set_flash_error(request, "Parquet Rolling Backup is disabled: Permanent S3 Bucket is not enabled. Please enable S3 in S3 Settings.")
        return RedirectResponse("/settings/backup", status_code=302)

    s3_ok, s3_msg = test_s3_connection(s3_config, bucket_type="permanent")
    if not s3_ok:
        set_flash_error(request, f"Parquet Rolling Backup is disabled: Permanent S3 Bucket connection failed ({s3_msg}).")
        return RedirectResponse("/settings/backup", status_code=302)

    try:
        from app.services.parquet_backup_service import run_daily_parquet_rolling_backup
        res = run_daily_parquet_rolling_backup(db)
        set_flash_success(
            request,
            f"Parquet rolling backup complete for cutoff date '{res['cutoff_date']}'! "
            f"Exported {res['total_tables']} operational tables ({res['total_records']} total records) to "
            f"directory '{res['directory_structure']}' in Permanent S3 Bucket '{res['target_bucket']}'."
        )
    except Exception as e:
        set_flash_error(request, f"Parquet rolling backup failed: {str(e)}")
    return RedirectResponse("/settings/backup", status_code=302)

