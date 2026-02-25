"""RAG document management endpoints.

Provides endpoints for uploading documents to the knowledge base,
listing ingested documents, and deleting documents.
"""

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.core.rag.ingest import (
    SUPPORTED_EXTENSIONS,
    delete_document,
    ingest_document,
    list_documents,
)
from app.utils.auth import verify_token

router = APIRouter()
security = HTTPBearer()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _get_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Extract user_id from JWT token."""
    user_id = verify_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id


@router.post("/upload")
@limiter.limit("20 per minute")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Depends(_get_user_id),
):
    """Upload and ingest a document into the RAG knowledge base.

    Supports: PDF, TXT, Markdown, DOCX.
    The document is parsed, chunked, embedded, and stored in Qdrant.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    import os

    _, ext = os.path.splitext(file.filename.lower())
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: {', '.join(SUPPORTED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size: {MAX_FILE_SIZE // 1024 // 1024}MB")

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    try:
        result = await ingest_document(
            filename=file.filename,
            content=content,
            user_id=user_id,
        )
        logger.info(
            "document_upload_success",
            doc_id=result.doc_id,
            filename=result.filename,
            chunk_count=result.chunk_count,
            user_id=user_id,
        )
        return {
            "doc_id": result.doc_id,
            "filename": result.filename,
            "file_type": result.file_type,
            "chunk_count": result.chunk_count,
            "created_at": result.created_at,
            "file_size": result.file_size,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("document_upload_failed", filename=file.filename, error=str(e))
        raise HTTPException(status_code=500, detail=f"Document ingestion failed: {str(e)}")


@router.get("/documents")
@limiter.limit("30 per minute")
async def get_documents(
    request: Request,
    user_id: str = Depends(_get_user_id),
):
    """List all documents in the RAG knowledge base."""
    try:
        docs = await list_documents(user_id=user_id)
        return {"documents": docs, "total": len(docs)}
    except Exception as e:
        logger.exception("document_list_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")


@router.delete("/documents/{doc_id}")
@limiter.limit("20 per minute")
async def remove_document(
    request: Request,
    doc_id: str,
    user_id: str = Depends(_get_user_id),
):
    """Delete a document and all its chunks from the knowledge base."""
    try:
        await delete_document(doc_id=doc_id)
        logger.info("document_delete_success", doc_id=doc_id, user_id=user_id)
        return {"doc_id": doc_id, "deleted": True}
    except Exception as e:
        logger.exception("document_delete_failed", doc_id=doc_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")
