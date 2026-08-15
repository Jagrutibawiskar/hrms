from fastapi import APIRouter, File, Form, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.core.deps import CurrentUser, Perm
from app.core.exceptions import Forbidden, NotFound
from app.core.rbac import P
from app.models.document import EmployeeDocument
from app.models.enums import DocumentType, NotificationEvent
from app.schemas.common import Message
from app.schemas.misc import DocumentOut, DocumentUpdate
from app.services import employee_service, notification_service
from app.utils.files import absolute_path, delete_file, save_upload

router = APIRouter(prefix="/documents", tags=["Documents"])

ManageAccess = Perm(P.DOCUMENT_MANAGE)


def to_out(doc: EmployeeDocument) -> DocumentOut:
    return DocumentOut(
        id=doc.id,
        employee_id=doc.employee_id,
        employee_name=doc.employee.full_name if doc.employee else None,
        document_type=doc.document_type,
        title=doc.title,
        description=doc.description,
        file_name=doc.file_name,
        mime_type=doc.mime_type,
        size_bytes=doc.size_bytes,
        is_visible_to_employee=doc.is_visible_to_employee,
        uploaded_by_user_id=doc.uploaded_by_user_id,
        created_at=doc.created_at,
    )


def _readable(principal, doc: EmployeeDocument) -> bool:
    if principal.has(P.DOCUMENT_READ_ALL, P.DOCUMENT_MANAGE):
        return True
    me = principal.employee
    return me is not None and doc.employee_id == me.id and doc.is_visible_to_employee


def _require_doc(principal, document_id: int) -> EmployeeDocument:
    doc = principal.db.get(EmployeeDocument, document_id)
    if doc is None or doc.company_id != principal.tenant_id:
        raise NotFound("Document not found")
    return doc


@router.get("/me", response_model=list[DocumentOut])
def my_documents(principal: CurrentUser):
    principal.require(P.DOCUMENT_READ_SELF)
    employee = principal.employee_or_404
    rows = principal.db.scalars(
        select(EmployeeDocument)
        .where(
            EmployeeDocument.employee_id == employee.id,
            EmployeeDocument.is_visible_to_employee.is_(True),
        )
        .order_by(EmployeeDocument.created_at.desc())
    )
    return [to_out(d) for d in rows]


@router.get("/employee/{employee_id}", response_model=list[DocumentOut])
def employee_documents(employee_id: int, principal: CurrentUser):
    employee_service.require_employee(principal.db, principal.tenant_id, employee_id)

    stmt = select(EmployeeDocument).where(EmployeeDocument.employee_id == employee_id)
    if not principal.has(P.DOCUMENT_READ_ALL, P.DOCUMENT_MANAGE):
        me = principal.employee
        if me is None or me.id != employee_id:
            raise Forbidden("You can only view your own documents")
        stmt = stmt.where(EmployeeDocument.is_visible_to_employee.is_(True))

    rows = principal.db.scalars(stmt.order_by(EmployeeDocument.created_at.desc()))
    return [to_out(d) for d in rows]


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    principal: ManageAccess,
    employee_id: int = Form(...),
    title: str = Form(...),
    document_type: DocumentType = Form(DocumentType.OTHER),
    description: str | None = Form(None),
    is_visible_to_employee: bool = Form(True),
    file: UploadFile = File(...),
):
    employee = employee_service.require_employee(principal.db, principal.tenant_id, employee_id)
    rel_path, size = save_upload(file, f"company_{principal.tenant_id}/employee_{employee_id}")

    doc = EmployeeDocument(
        company_id=principal.tenant_id,
        employee_id=employee_id,
        document_type=document_type,
        title=title,
        description=description,
        file_name=file.filename or "document",
        file_path=rel_path,
        mime_type=file.content_type,
        size_bytes=size,
        is_visible_to_employee=is_visible_to_employee,
        uploaded_by_user_id=principal.user_id,
    )
    principal.db.add(doc)
    principal.db.flush()

    if is_visible_to_employee:
        notification_service.notify_employee(
            principal.db,
            employee,
            event=NotificationEvent.DOCUMENT_UPLOADED,
            title="New document available",
            message=f"'{title}' has been added to your documents.",
            entity_type="document",
            entity_id=doc.id,
            action_url="/documents",
        )
    principal.db.commit()
    principal.db.refresh(doc)
    return to_out(doc)


@router.get("/{document_id}/download")
def download_document(document_id: int, principal: CurrentUser):
    doc = _require_doc(principal, document_id)
    if not _readable(principal, doc):
        raise Forbidden("You do not have access to this document")

    path = absolute_path(doc.file_path)
    if not path.exists():
        raise NotFound("The stored file is missing")
    return FileResponse(
        path, filename=doc.file_name, media_type=doc.mime_type or "application/octet-stream"
    )


@router.patch("/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: int, payload: DocumentUpdate, principal: ManageAccess
):
    doc = _require_doc(principal, document_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(doc, field, value)
    principal.db.commit()
    principal.db.refresh(doc)
    return to_out(doc)


@router.delete("/{document_id}", response_model=Message)
def delete_document(document_id: int, principal: ManageAccess):
    doc = _require_doc(principal, document_id)
    stored_path = doc.file_path
    principal.db.delete(doc)
    principal.db.commit()
    delete_file(stored_path)
    return Message(message="Document deleted")
