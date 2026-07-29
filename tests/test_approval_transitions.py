import asyncio
from datetime import date

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.models.attendance import ApprovalStatus, Attendance
from app.models.expense import ExpenseStatus
from app.models.leave import LeaveStatus
from app.models.payment import PaymentStatus
from app.models.timesheet import TimesheetApproval
from app.routers.admin_leaves import approve_leave, reject_leave
from app.routers.attendance import (
    attendance_approve,
    attendance_reject,
    timesheet_approve,
    timesheet_reject,
)
from app.routers.expenses import expense_approve, expense_reject
from app.routers.payments import payment_reject, payment_verify


def _request(path="/acceptance"):
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [],
            "session": {},
        }
    )


def _run(coro):
    return asyncio.run(coro)


def test_expense_and_leave_transitions_are_terminal_and_require_reason(
    db_session, acceptance_data, operational_data
):
    manager = acceptance_data["users"]["l3"]
    expense = operational_data["expense"]
    expense.status = ExpenseStatus.submitted
    leave = operational_data["leave"]
    leave.status = LeaveStatus.pending
    db_session.commit()

    _run(expense_approve(expense.id, _request(), manager, db_session))
    assert expense.status == ExpenseStatus.approved
    with pytest.raises(HTTPException) as exc:
        _run(expense_approve(expense.id, _request(), manager, db_session))
    assert exc.value.status_code == 409
    expense.status = ExpenseStatus.submitted
    db_session.commit()
    _run(
        expense_reject(
            expense.id, _request(), manager, db_session, "Receipt mismatch"
        )
    )
    assert expense.status == ExpenseStatus.rejected

    leave.status = LeaveStatus.pending
    db_session.commit()
    with pytest.raises(HTTPException) as exc:
        _run(reject_leave(leave.id, "", manager, db_session))
    assert exc.value.status_code == 400
    _run(reject_leave(leave.id, "Insufficient coverage", manager, db_session))
    assert leave.status == LeaveStatus.rejected
    with pytest.raises(HTTPException) as exc:
        _run(approve_leave(leave.id, manager, db_session))
    assert exc.value.status_code == 409
    leave.status = LeaveStatus.pending
    db_session.commit()
    _run(approve_leave(leave.id, manager, db_session))
    assert leave.status == LeaveStatus.approved


def test_attendance_timesheet_and_payment_transitions_are_one_way(
    db_session, acceptance_data, operational_data
):
    manager = acceptance_data["users"]["l3"]
    rep = acceptance_data["users"]["l1"]
    attendance = Attendance(
        user_id=rep.id,
        date=date(2026, 1, 15),
        approval_status=ApprovalStatus.pending,
    )
    db_session.add(attendance)
    timesheet = operational_data["timesheet"]
    timesheet.approval_status = TimesheetApproval.pending
    payment = operational_data["payment"]
    payment.status = PaymentStatus.collected
    db_session.commit()

    _run(
        attendance_approve(
            attendance.id, _request(), manager, db_session, "full_day"
        )
    )
    assert attendance.approval_status == ApprovalStatus.approved
    with pytest.raises(HTTPException) as exc:
        _run(attendance_reject(attendance.id, _request(), manager, db_session, "x"))
    assert exc.value.status_code == 409
    attendance.approval_status = ApprovalStatus.pending
    db_session.commit()
    _run(
        attendance_reject(
            attendance.id, _request(), manager, db_session, "Hours mismatch"
        )
    )
    assert attendance.approval_status == ApprovalStatus.rejected

    _run(timesheet_approve(timesheet.id, _request(), manager, db_session))
    assert timesheet.approval_status == TimesheetApproval.approved
    with pytest.raises(HTTPException) as exc:
        _run(timesheet_reject(timesheet.id, _request(), manager, db_session, "x"))
    assert exc.value.status_code == 409
    timesheet.approval_status = TimesheetApproval.pending
    db_session.commit()
    _run(
        timesheet_reject(
            timesheet.id, _request(), manager, db_session, "Activity mismatch"
        )
    )
    assert timesheet.approval_status == TimesheetApproval.rejected

    _run(payment_verify(payment.id, _request(), manager, db_session))
    assert payment.status == PaymentStatus.verified
    with pytest.raises(HTTPException) as exc:
        _run(payment_reject(payment.id, _request(), manager, db_session))
    assert exc.value.status_code == 409
    payment.status = PaymentStatus.collected
    db_session.commit()
    _run(payment_reject(payment.id, _request(), manager, db_session))
    assert payment.status == PaymentStatus.rejected
