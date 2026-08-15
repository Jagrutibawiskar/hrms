from fastapi import APIRouter

from app.api.v1 import (
    attendance,
    auth,
    companies,
    compliance,
    dashboard,
    documents,
    employees,
    holidays,
    hr,
    leaves,
    notifications,
    onboarding,
    organization,
    payroll,
    reports,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(companies.router)
api_router.include_router(compliance.router)
api_router.include_router(onboarding.router)
api_router.include_router(organization.router)
api_router.include_router(employees.router)
api_router.include_router(hr.router)
api_router.include_router(attendance.router)
api_router.include_router(leaves.router)
api_router.include_router(holidays.router)
api_router.include_router(payroll.router)
api_router.include_router(documents.router)
api_router.include_router(notifications.router)
api_router.include_router(reports.router)
api_router.include_router(dashboard.router)
