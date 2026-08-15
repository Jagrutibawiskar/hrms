import csv
import io
from datetime import date

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.core.deps import Perm
from app.core.rbac import P
from app.models.attendance import Attendance
from app.models.employee import Employee, EmployeeEmploymentDetail
from app.models.enums import LeaveStatus
from app.models.leave import LeaveRequest
from app.models.payroll import PayrollItem, PayrollRun
from app.utils.dates import today

router = APIRouter(prefix="/reports", tags=["Reports"])

Access = Perm(P.REPORT_VIEW)


def csv_response(filename: str, columns: list[str], rows: list[dict]) -> StreamingResponse:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def respond(export: bool, filename: str, columns: list[str], rows: list[dict]):
    if export:
        return csv_response(filename, columns, rows)
    return {"columns": columns, "rows": rows, "count": len(rows)}


@router.get("/employees")
def employee_report(
    principal: Access,
    department_id: int | None = None,
    status_: str | None = Query(None, alias="status"),
    export: bool = False,
):
    stmt = (
        select(Employee, EmployeeEmploymentDetail)
        .join(
            EmployeeEmploymentDetail,
            EmployeeEmploymentDetail.employee_id == Employee.id,
            isouter=True,
        )
        .where(Employee.company_id == principal.tenant_id)
    )
    if department_id:
        stmt = stmt.where(EmployeeEmploymentDetail.department_id == department_id)
    if status_:
        stmt = stmt.where(Employee.status == status_)

    rows = []
    for employee, detail in principal.db.execute(stmt.order_by(Employee.employee_code)).all():
        manager = (
            principal.db.get(Employee, detail.manager_id)
            if detail and detail.manager_id
            else None
        )
        rows.append(
            {
                "employee_code": employee.employee_code,
                "name": employee.full_name,
                "work_email": employee.work_email,
                "department": detail.department.name if detail and detail.department else "",
                "designation": detail.designation.name if detail and detail.designation else "",
                "location": detail.location.name if detail and detail.location else "",
                "manager": manager.full_name if manager else "",
                "joining_date": str(detail.joining_date) if detail else "",
                "employment_type": detail.employment_type.value if detail else "",
                "status": employee.status.value,
            }
        )

    columns = [
        "employee_code", "name", "work_email", "department", "designation",
        "location", "manager", "joining_date", "employment_type", "status",
    ]
    return respond(export, "employee_report.csv", columns, rows)


@router.get("/attendance")
def attendance_report(
    principal: Access,
    from_date: date | None = None,
    to_date: date | None = None,
    department_id: int | None = None,
    employee_id: int | None = None,
    export: bool = False,
):
    end = to_date or today()
    start = from_date or end.replace(day=1)

    stmt = select(Attendance).where(
        Attendance.company_id == principal.tenant_id,
        Attendance.date >= start,
        Attendance.date <= end,
    )
    if employee_id:
        stmt = stmt.where(Attendance.employee_id == employee_id)
    if department_id:
        stmt = stmt.where(
            Attendance.employee_id.in_(
                select(EmployeeEmploymentDetail.employee_id).where(
                    EmployeeEmploymentDetail.department_id == department_id
                )
            )
        )

    rows = [
        {
            "employee_code": r.employee.employee_code if r.employee else "",
            "name": r.employee.full_name if r.employee else "",
            "date": str(r.date),
            "check_in": r.check_in.isoformat() if r.check_in else "",
            "check_out": r.check_out.isoformat() if r.check_out else "",
            "working_hours": float(r.working_hours),
            "status": r.status.value,
            "late_minutes": int(r.late_minutes or 0),
            "regularized": "yes" if r.is_regularized else "no",
        }
        for r in principal.db.scalars(
            stmt.order_by(Attendance.date.desc(), Attendance.employee_id)
        )
    ]
    columns = [
        "employee_code", "name", "date", "check_in", "check_out",
        "working_hours", "status", "late_minutes", "regularized",
    ]
    return respond(export, f"attendance_{start}_{end}.csv", columns, rows)


@router.get("/leaves")
def leave_report(
    principal: Access,
    from_date: date | None = None,
    to_date: date | None = None,
    department_id: int | None = None,
    employee_id: int | None = None,
    status_: LeaveStatus | None = Query(None, alias="status"),
    export: bool = False,
):
    stmt = select(LeaveRequest).where(LeaveRequest.company_id == principal.tenant_id)
    if from_date:
        stmt = stmt.where(LeaveRequest.to_date >= from_date)
    if to_date:
        stmt = stmt.where(LeaveRequest.from_date <= to_date)
    if employee_id:
        stmt = stmt.where(LeaveRequest.employee_id == employee_id)
    if status_:
        stmt = stmt.where(LeaveRequest.status == status_)
    if department_id:
        stmt = stmt.where(
            LeaveRequest.employee_id.in_(
                select(EmployeeEmploymentDetail.employee_id).where(
                    EmployeeEmploymentDetail.department_id == department_id
                )
            )
        )

    rows = [
        {
            "employee_code": r.employee.employee_code if r.employee else "",
            "name": r.employee.full_name if r.employee else "",
            "leave_type": r.leave_type.name if r.leave_type else "",
            "from_date": str(r.from_date),
            "to_date": str(r.to_date),
            "days": float(r.days),
            "status": r.status.value,
            "reason": r.reason,
            "applied_at": r.applied_at.isoformat(),
            "actioned_at": r.actioned_at.isoformat() if r.actioned_at else "",
        }
        for r in principal.db.scalars(stmt.order_by(LeaveRequest.from_date.desc()))
    ]
    columns = [
        "employee_code", "name", "leave_type", "from_date", "to_date",
        "days", "status", "reason", "applied_at", "actioned_at",
    ]
    return respond(export, "leave_report.csv", columns, rows)


@router.get("/payroll")
def payroll_report(
    principal: Access,
    year: int | None = None,
    month: int | None = None,
    department_id: int | None = None,
    export: bool = False,
):
    stmt = (
        select(PayrollItem, PayrollRun)
        .join(PayrollRun, PayrollRun.id == PayrollItem.payroll_run_id)
        .where(PayrollItem.company_id == principal.tenant_id)
    )
    if year:
        stmt = stmt.where(PayrollRun.year == year)
    if month:
        stmt = stmt.where(PayrollRun.month == month)
    if department_id:
        stmt = stmt.where(
            PayrollItem.employee_id.in_(
                select(EmployeeEmploymentDetail.employee_id).where(
                    EmployeeEmploymentDetail.department_id == department_id
                )
            )
        )

    rows = [
        {
            "period": f"{run.month:02d}/{run.year}",
            "employee_code": item.employee.employee_code if item.employee else "",
            "name": item.employee.full_name if item.employee else "",
            "working_days": float(item.working_days),
            "paid_days": float(item.paid_days),
            "lop_days": float(item.lop_days),
            "gross_earnings": float(item.gross_earnings),
            "total_deductions": float(item.total_deductions),
            "net_pay": float(item.net_pay),
            "payroll_status": run.status.value,
        }
        for item, run in principal.db.execute(
            stmt.order_by(PayrollRun.year.desc(), PayrollRun.month.desc())
        ).all()
    ]
    columns = [
        "period", "employee_code", "name", "working_days", "paid_days", "lop_days",
        "gross_earnings", "total_deductions", "net_pay", "payroll_status",
    ]
    return respond(export, "payroll_report.csv", columns, rows)


@router.get("/headcount")
def headcount_report(principal: Access):
    """Active headcount grouped by department — the one aggregate MVP-1 needs."""
    from app.models.organization import Department

    rows = principal.db.execute(
        select(Department.name, func.count(EmployeeEmploymentDetail.id))
        .join(
            EmployeeEmploymentDetail,
            EmployeeEmploymentDetail.department_id == Department.id,
            isouter=True,
        )
        .where(Department.company_id == principal.tenant_id)
        .group_by(Department.name)
        .order_by(Department.name)
    ).all()
    return {"rows": [{"department": name, "headcount": count} for name, count in rows]}
