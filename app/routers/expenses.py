import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import (get_db, require_web_auth, require_web_roles,
                            require_restricted_module_web_access)
from app.models.expense import Expense, ExpenseCategory, ExpenseStatus
from app.models.user import User, UserRole
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate
from app.services.access_control import (
    require_expense_access,
    scope_employee_record_query,
)
from app.utils.s3_service import upload_image_file

ALLOWED_RECEIPT_EXTS = {".jpg", ".jpeg", ".png", ".pdf"}
MAX_RECEIPT_SIZE = 5 * 1024 * 1024  # 5 MB

router = APIRouter(prefix="/operations/expenses", tags=["expenses"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def expense_list(
    request: Request,
    current_user: User = Depends(require_restricted_module_web_access),
    db: Session = Depends(get_db),
    status: str = Query(default=""),
    category: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = scope_employee_record_query(db.query(Expense), Expense, current_user, db)
    if status and status in [s.value for s in ExpenseStatus]:
        query = query.filter(Expense.status == status)
    if category and category in [c.value for c in ExpenseCategory]:
        query = query.filter(Expense.category == category)
    query = query.order_by(Expense.created_at.desc())
    pagination = paginate(query, page)
    return templates.TemplateResponse("expenses/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "status": status, "category": category,
        "ExpenseStatus": ExpenseStatus, "ExpenseCategory": ExpenseCategory,
        **get_flash(request),
    })


@router.get("/new", response_class=HTMLResponse)
async def expense_new(
    request: Request,
    current_user: User = Depends(require_web_auth),
):
    return templates.TemplateResponse("expenses/form.html", {
        "request": request, "current_user": current_user,
        "item": None, "ExpenseCategory": ExpenseCategory, "error": None,
    })


@router.post("/new")
async def expense_create(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    form = await request.form()
    category_val = form.get("category", "")
    amount_val = form.get("amount", "")
    expense_date = form.get("expense_date", "")
    description = form.get("description", "")
    receipt_file = form.get("receipt")

    try:
        amt = float(amount_val)
        cat = ExpenseCategory(category_val)
    except (ValueError, KeyError):
        return templates.TemplateResponse("expenses/form.html", {
            "request": request, "current_user": current_user,
            "item": None, "ExpenseCategory": ExpenseCategory,
            "error": "Invalid amount or category.",
        })

    # Handle receipt upload
    receipt_url = None
    if receipt_file and hasattr(receipt_file, "filename") and receipt_file.filename:
        ext = os.path.splitext(receipt_file.filename)[1].lower()
        if ext not in ALLOWED_RECEIPT_EXTS:
            return templates.TemplateResponse("expenses/form.html", {
                "request": request, "current_user": current_user,
                "item": None, "ExpenseCategory": ExpenseCategory,
                "error": f"Receipt file type not allowed. Use: {', '.join(ALLOWED_RECEIPT_EXTS)}",
            })

        contents = await receipt_file.read()
        if len(contents) > MAX_RECEIPT_SIZE:
            return templates.TemplateResponse("expenses/form.html", {
                "request": request, "current_user": current_user,
                "item": None, "ExpenseCategory": ExpenseCategory,
                "error": "Receipt file too large. Maximum 5MB.",
            })

        receipt_url = upload_image_file(
            db,
            contents,
            receipt_file.filename,
            folder_prefix="receipts",
            content_type=receipt_file.content_type or "application/octet-stream",
            bucket_type="files",
        )

    e = Expense(
        user_id=current_user.id,
        category=cat,
        amount=amt,
        expense_date=expense_date,
        description=description or None,
        receipt_url=receipt_url,
        status=ExpenseStatus.submitted,
    )
    db.add(e)
    db.commit()
    set_flash_success(request, "Expense submitted.")
    return RedirectResponse("/operations/expenses", status_code=302)


@router.post("/{expense_id}/upload-receipt")
async def expense_upload_receipt(
    expense_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    """Upload or replace receipt for an existing expense."""
    try:
        expense = require_expense_access(db, current_user, expense_id)
    except HTTPException:
        set_flash_error(request, "Expense not found.")
        return RedirectResponse("/operations/expenses", status_code=302)

    form = await request.form()
    receipt_file = form.get("receipt")

    if not receipt_file or not hasattr(receipt_file, "filename") or not receipt_file.filename:
        set_flash_error(request, "No file selected.")
        return RedirectResponse(f"/operations/expenses", status_code=302)

    ext = os.path.splitext(receipt_file.filename)[1].lower()
    if ext not in ALLOWED_RECEIPT_EXTS:
        set_flash_error(request, f"File type not allowed. Use: {', '.join(ALLOWED_RECEIPT_EXTS)}")
        return RedirectResponse("/operations/expenses", status_code=302)

    contents = await receipt_file.read()
    if len(contents) > MAX_RECEIPT_SIZE:
        set_flash_error(request, "File too large. Maximum 5MB.")
        return RedirectResponse("/operations/expenses", status_code=302)

    expense.receipt_url = upload_image_file(
        db,
        contents,
        receipt_file.filename,
        folder_prefix="receipts",
        content_type=receipt_file.content_type or "application/octet-stream",
        bucket_type="files",
    )
    db.commit()
    set_flash_success(request, f"Receipt uploaded for expense #{expense_id}.")
    return RedirectResponse("/operations/expenses", status_code=302)


@router.post("/{expense_id}/approve")
async def expense_approve(
    expense_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    item = require_expense_access(db, current_user, expense_id)
    if item.status != ExpenseStatus.submitted:
        raise HTTPException(status_code=409, detail="Expense is not awaiting approval.")
    item.status = ExpenseStatus.approved
    item.approved_by_id = current_user.id
    item.approved_at = datetime.now()
    db.commit()
    set_flash_success(request, f"Expense #{expense_id} approved.")
    return RedirectResponse("/operations/expenses", status_code=302)


@router.post("/{expense_id}/reject")
async def expense_reject(
    expense_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    reason: Optional[str] = Form(default=None),
):
    item = require_expense_access(db, current_user, expense_id)
    if item.status != ExpenseStatus.submitted:
        raise HTTPException(status_code=409, detail="Expense is not awaiting review.")
    if not (reason or "").strip():
        raise HTTPException(status_code=400, detail="Rejection reason is required.")
    item.status = ExpenseStatus.rejected
    item.rejection_reason = reason.strip()
    db.commit()
    set_flash_error(request, f"Expense #{expense_id} rejected.")
    return RedirectResponse("/expenses", status_code=302)
