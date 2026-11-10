"""
Conversation routes: /conversations/*.

Thin layer — delegates to conversation repository, no business logic.
"""

import logging
import time
import uuid

from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    ConversationCreateRequest,
    ConversationDeleteResponse,
    ConversationItem,
    ConversationListResponse,
    ConversationMessageItem,
    ConversationUpdateRequest,
)
from app.core.domain import Conversation, ConversationMessage
from app.core.ports import ConversationRepositoryPort

logger = logging.getLogger(__name__)


def create_conversations_router(
    conversation_repo: ConversationRepositoryPort | None = None,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/conversations",
        response_model=ConversationItem,
        status_code=201,
        tags=["Conversations"],
    )
    def create_conversation(request: ConversationCreateRequest):
        """Create a new conversation."""
        if conversation_repo is None:
            raise HTTPException(
                status_code=501,
                detail="Conversation history is not available (conversation_repo not injected)",
            )
        try:
            now = time.time()
            conv = Conversation(
                id=str(uuid.uuid4()),
                title=request.title,
                messages=[
                    ConversationMessage(
                        role=m.role,
                        content=m.content,
                        timestamp=m.timestamp or now,
                    )
                    for m in request.messages
                ],
                created_at=now,
                updated_at=now,
            )
            conversation_repo.save(conv)
            return ConversationItem(
                id=conv.id,
                title=conv.title,
                messages=[
                    ConversationMessageItem(
                        role=m.role,
                        content=m.content,
                        timestamp=m.timestamp,
                    )
                    for m in conv.messages
                ],
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
        except Exception as e:
            logger.exception("Failed to create conversation")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get(
        "/conversations", response_model=ConversationListResponse, tags=["Conversations"]
    )
    def list_conversations(limit: int = 50, offset: int = 0):
        """
        List all conversations, most recent first.
        """
        if conversation_repo is None:
            raise HTTPException(
                status_code=501,
                detail="Conversation history is not available (conversation_repo not injected)",
            )
        try:
            convos = conversation_repo.list_all(limit=limit, offset=offset)
            total = conversation_repo.count()
            return ConversationListResponse(
                total=total,
                conversations=[
                    ConversationItem(
                        id=c.id,
                        title=c.title,
                        messages=[
                            ConversationMessageItem(
                                role=m.role,
                                content=m.content,
                                timestamp=m.timestamp,
                            )
                            for m in c.messages
                        ],
                        created_at=c.created_at,
                        updated_at=c.updated_at,
                    )
                    for c in convos
                ],
            )
        except Exception as e:
            logger.exception("Failed to list conversations")
            raise HTTPException(status_code=500, detail=str(e))

    @router.get(
        "/conversations/{conv_id}", response_model=ConversationItem, tags=["Conversations"]
    )
    def get_conversation(conv_id: str):
        """Get a single conversation with all its messages."""
        if conversation_repo is None:
            raise HTTPException(
                status_code=501,
                detail="Conversation history is not available (conversation_repo not injected)",
            )
        try:
            conv = conversation_repo.get(conv_id)
            if conv is None:
                raise HTTPException(status_code=404, detail="Conversation not found")
            return ConversationItem(
                id=conv.id,
                title=conv.title,
                messages=[
                    ConversationMessageItem(
                        role=m.role,
                        content=m.content,
                        timestamp=m.timestamp,
                    )
                    for m in conv.messages
                ],
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Failed to get conversation")
            raise HTTPException(status_code=500, detail=str(e))

    @router.put(
        "/conversations/{conv_id}", response_model=ConversationItem, tags=["Conversations"]
    )
    def update_conversation(conv_id: str, request: ConversationUpdateRequest):
        """Update a conversation's title and/or messages."""
        if conversation_repo is None:
            raise HTTPException(
                status_code=501,
                detail="Conversation history is not available (conversation_repo not injected)",
            )
        try:
            conv = conversation_repo.get(conv_id)
            if conv is None:
                raise HTTPException(status_code=404, detail="Conversation not found")

            if request.title is not None:
                conv.title = request.title
            if request.messages is not None:
                conv.messages = [
                    ConversationMessage(
                        role=m.role,
                        content=m.content,
                        timestamp=m.timestamp,
                    )
                    for m in request.messages
                ]
            conv.updated_at = time.time()
            conversation_repo.save(conv)
            return ConversationItem(
                id=conv.id,
                title=conv.title,
                messages=[
                    ConversationMessageItem(
                        role=m.role,
                        content=m.content,
                        timestamp=m.timestamp,
                    )
                    for m in conv.messages
                ],
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Failed to update conversation")
            raise HTTPException(status_code=500, detail=str(e))

    @router.delete(
        "/conversations/{conv_id}",
        response_model=ConversationDeleteResponse,
        tags=["Conversations"],
    )
    def delete_conversation(conv_id: str):
        """Delete a conversation."""
        if conversation_repo is None:
            raise HTTPException(
                status_code=501,
                detail="Conversation history is not available (conversation_repo not injected)",
            )
        try:
            deleted = conversation_repo.delete(conv_id)
            return ConversationDeleteResponse(
                status="success" if deleted else "not_found",
                deleted=deleted,
            )
        except Exception as e:
            logger.exception("Failed to delete conversation")
            raise HTTPException(status_code=500, detail=str(e))

    return router
