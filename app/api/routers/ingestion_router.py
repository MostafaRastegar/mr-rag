"""
Ingestion routes: /ingest.

Thin layer — delegates to IngestionPipeline, no business logic.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.api.schemas import IngestRequest, IngestResponse
from app.core.exceptions import DocumentLoadError, IngestionError
from app.pipeline.ingestion import IngestionPipeline

logger = logging.getLogger(__name__)


def create_ingestion_router(ingestion: IngestionPipeline) -> APIRouter:
    router = APIRouter()

    @router.post("/ingest", response_model=IngestResponse, tags=["Ingestion"])
    def ingest(request: IngestRequest):
        """
        Ingest a JSON file into the vector store.
        """
        try:
            chunks = ingestion.run(request.file_path)
            return IngestResponse(
                status="success",
                chunks_ingested=chunks,
            )
        except (FileNotFoundError, DocumentLoadError) as e:
            raise HTTPException(status_code=404, detail=str(e))
        except IngestionError as e:
            logger.exception("Ingestion failed")
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            logger.exception("Unexpected ingestion error")
            raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    return router
