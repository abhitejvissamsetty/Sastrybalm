"""
Payment Submissions — Rep groups collected payments into a batch submission.
Manager approves → Posted as Journal Entry to ZAP.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_auth, require_web_roles
from app.models.payment import Payment, PaymentStatus
from app.models.payment_submission import PaymentSubmission, SubmissionStatus
from app.models.user import User, UserRole
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate
from app.utils.ref_generator import submission_ref

router = APIRouter(prefix="/payment-submissions", tags=["payment-submissions"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def submission_list(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = db.query(PaymentSubmission)
    if current_user.role == UserRole.field_rep:
        query = query.filter(PaymentSubmission.rep_id == current_user.id)
    if status and status in [s.value for s in SubmissionStatus]:
        query = query.filter(PaymentSubmission.status == status)
    query = query.order_by(PaymentSubmission.created_at.desc())
    pagination = paginate(query, page)
    return templates.TemplateResponse("payment_submissions/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "status": status,
        "SubmissionStatus": SubmissionStatus,
        **get_flash(request),
    })


@router.get("/new", response_class=HTMLResponse)
async def submission_new(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    # Show unsubmitted payments for this rep
    payments = db.query(Payment).filter(
        Payment.user_id == current_user.id,
        Payment.status.in_([PaymentStatus.collected, PaymentStatus.verified]),
        Payment.submission_id.is_(None),
    ).order_by(Payment.created_at.desc()).all()
    return templates.TemplateResponse("payment_submissions/form.html", {
        "request": request, "current_user": current_user,
        "payments": payments, "error": None,
    })


@router.post("/new")
async def submission_create(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    form = await request.form()
    payment_ids = form.getlist("payment_ids[]")
    notes = form.get("notes", "")
    target_account = form.get("target_account", "")

    if not payment_ids:
        payments = db.query(Payment).filter(
            Payment.user_id == current_user.id,
            Payment.status.in_([PaymentStatus.collected, PaymentStatus.verified]),
            Payment.submission_id.is_(None),
        ).all()
        return templates.TemplateResponse("payment_submissions/form.html", {
            "request": request, "current_user": current_user,
            "payments": payments, "error": "Select at least one payment.",
        })

    ref = submission_ref(db, PaymentSubmission)
    sub = PaymentSubmission(
        submission_ref=ref,
        rep_id=current_user.id,
        target_account=target_account or None,
        notes=notes or None,
    )
    db.add(sub)
    db.flush()

    total = 0
    d2000 = d500 = d200 = d100 = d50 = d20 = d10 = 0
    online_total = 0

    for pid in payment_ids:
        payment = db.query(Payment).filter(Payment.id == int(pid)).first()
        if payment and payment.user_id == current_user.id and payment.submission_id is None:
            payment.submission_id = sub.id
            total += float(payment.amount)
            d2000 += payment.denom_2000
            d500 += payment.denom_500
            d200 += payment.denom_200
            d100 += payment.denom_100
            d50 += payment.denom_50
            d20 += payment.denom_20
            d10 += payment.denom_10
            if payment.method.value != "cash":
                online_total += float(payment.amount)

    sub.total_amount = total
    sub.denom_2000_total = d2000
    sub.denom_500_total = d500
    sub.denom_200_total = d200
    sub.denom_100_total = d100
    sub.denom_50_total = d50
    sub.denom_20_total = d20
    sub.denom_10_total = d10
    sub.online_amount = online_total
    db.commit()

    set_flash_success(request, f"Payment submission {ref} created with {len(payment_ids)} payments.")
    return RedirectResponse("/payment-submissions", status_code=302)


@router.get("/{sub_id}", response_class=HTMLResponse)
async def submission_detail(
    sub_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    item = db.query(PaymentSubmission).filter(PaymentSubmission.id == sub_id).first()
    if not item:
        set_flash_error(request, "Submission not found.")
        return RedirectResponse("/payment-submissions", status_code=302)
    return templates.TemplateResponse("payment_submissions/detail.html", {
        "request": request, "current_user": current_user,
        "item": item, "SubmissionStatus": SubmissionStatus,
        **get_flash(request),
    })


@router.post("/{sub_id}/approve")
async def submission_approve(
    sub_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    from datetime import datetime
    item = db.query(PaymentSubmission).filter(PaymentSubmission.id == sub_id).first()
    if item and item.status == SubmissionStatus.pending:
        item.status = SubmissionStatus.approved
        item.approved_by_id = current_user.id
        item.approved_at = datetime.now()
        db.commit()
        set_flash_success(request, f"Submission {item.submission_ref} approved.")
    return RedirectResponse(f"/payment-submissions/{sub_id}", status_code=302)


@router.post("/{sub_id}/reject")
async def submission_reject(
    sub_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    reason: str = Form(default=""),
):
    item = db.query(PaymentSubmission).filter(PaymentSubmission.id == sub_id).first()
    if item and item.status == SubmissionStatus.pending:
        item.status = SubmissionStatus.rejected
        item.rejection_reason = reason or None
        db.commit()
        set_flash_error(request, f"Submission {item.submission_ref} rejected.")
    return RedirectResponse(f"/payment-submissions/{sub_id}", status_code=302)


@router.post("/{sub_id}/post")
async def submission_post(
    sub_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """Post approved submission as Journal Entry to ZAP."""
    item = db.query(PaymentSubmission).filter(PaymentSubmission.id == sub_id).first()
    if not item or item.status != SubmissionStatus.approved:
        set_flash_error(request, "Submission must be approved before posting.")
        return RedirectResponse(f"/payment-submissions/{sub_id}", status_code=302)

    item.status = SubmissionStatus.posted
    item.journal_entry_ref = f"JE-LOCAL-{item.id}"
    db.commit()
    set_flash_success(request, f"Payment submission '{item.submission_ref}' posted successfully.")
    return RedirectResponse(f"/payment-submissions/{sub_id}", status_code=302)
