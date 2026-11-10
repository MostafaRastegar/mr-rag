"""
Upload routes: /upload.

Thin layer — accepts a multipart file, stages it to a temp path, and
delegates ingestion to IngestionPipeline.
"""

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.api.schemas import UploadResponse
from app.core.exceptions import DocumentLoadError, IngestionError
from app.pipeline.ingestion import IngestionPipeline

logger = logging.getLogger(__name__)


def create_upload_router(ingestion: IngestionPipeline) -> APIRouter:
    router = APIRouter()

    @router.post("/upload", response_model=UploadResponse, tags=["Ingestion"])
    def upload(file: UploadFile = File(...)):
        """
        Upload a file and ingest it into the vector store.

        The uploaded file is staged to a temporary location, ingested
        (load → split → embed → store), then the temp file is removed.
        """
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        # Stage to a temp file preserving the extension so the loader can
        # auto-detect the format.
        suffix = Path(file.filename).suffix
        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp_path = tmp.name
                tmp.write(file.file.read())

            chunks = ingestion.run(tmp_path, original_filename=file.filename)

            return UploadResponse(
                status="success",
                file_name=file.filename,
                chunks_ingested=chunks,
                message=f"Ingested {chunks} chunks from {file.filename}",
            )
        except (FileNotFoundError, DocumentLoadError) as e:
            raise HTTPException(status_code=404, detail=str(e))
        except IngestionError as e:
            logger.exception("Upload ingestion failed")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.exception("Unexpected upload error")
            raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
        finally:
            if tmp_path is not None:
                Path(tmp_path).unlink(missing_ok=True)

    return router
