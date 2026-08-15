import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.core.schema_sync import sync_schema
from app.core.seed import seed_roles_and_permissions
from app.models import Base

logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG)
logger = logging.getLogger("hrms")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    if settings.AUTO_CREATE_TABLES:
        # Dev convenience. In production run `alembic upgrade head` instead.
        Base.metadata.create_all(bind=engine)
        # create_all() only adds new tables — bring existing ones up to date too.
        sync_schema(engine)

    with SessionLocal() as db:
        seed_roles_and_permissions(db)
    logger.info("HRMS API ready (%s)", settings.ENVIRONMENT)
    yield


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    version="1.0.0-mvp1",
    description=(
        "Multi-tenant HRMS backend: authentication, company onboarding, employees, "
        "attendance, leave, holidays, payroll, documents, notifications and reports."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Company logos are public branding, so they're served directly. Employee documents
# are deliberately NOT here — they stay behind GET /documents/{id}/download.
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=settings.UPLOAD_DIR), name="static")


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = [
        {"field": ".".join(str(p) for p in err["loc"][1:]) or "body", "message": err["msg"]}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation failed", "errors": errors},
    )


@app.exception_handler(IntegrityError)
async def integrity_handler(request: Request, exc: IntegrityError):
    logger.warning("Integrity error on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "This operation conflicts with existing data"},
    )


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "app": settings.APP_NAME, "environment": settings.ENVIRONMENT}


@app.get("/", tags=["System"])
def root():
    return {
        "name": f"{settings.APP_NAME} API",
        "version": app.version,
        "docs": "/docs",
        "api": settings.API_V1_PREFIX,
    }


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
