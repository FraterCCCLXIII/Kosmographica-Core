import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal, get_db
from app.models.conversation import Conversation, ConversationMessage
from app.models.workspace import Project, Workspace
from app.providers.factory import get_embedding_provider, get_llm_provider
from app.services.rag import RAGService

router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationCreate(BaseModel):
    workspace_id: uuid.UUID
    project_id: uuid.UUID | None = None
    title: str = Field(default="New conversation", min_length=1)
    mode: str = "single"
    context: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    status: str | None = None
    context: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class MessageCreate(BaseModel):
    content: str = Field(min_length=1)
    mode: str | None = None
    k: int = Field(default=8, ge=1, le=50)
    filters: dict[str, Any] = Field(default_factory=dict)
    project_ids: list[uuid.UUID] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_conversation(request: ConversationCreate, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    await _ensure_workspace(request.workspace_id, db)
    if request.project_id is not None:
        await _ensure_project_in_workspace(request.workspace_id, request.project_id, db)

    conversation = Conversation(
        workspace_id=request.workspace_id,
        project_id=request.project_id,
        title=request.title,
        mode=request.mode,
        status="active",
        context=request.context,
        metadata_=request.metadata,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return {"message": "Conversation created.", "data": _serialize_conversation(conversation, [])}


@router.get("")
async def list_conversations(
    workspace_id: uuid.UUID = Query(...),
    project_id: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    query: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    await _ensure_workspace(workspace_id, db)
    statement = select(Conversation).where(Conversation.workspace_id == workspace_id)
    count_statement = select(func.count()).select_from(Conversation).where(Conversation.workspace_id == workspace_id)

    if project_id == "none":
        statement = statement.where(Conversation.project_id.is_(None))
        count_statement = count_statement.where(Conversation.project_id.is_(None))
    elif project_id:
        parsed_project_id = _parse_uuid(project_id, "project_id")
        await _ensure_project_in_workspace(workspace_id, parsed_project_id, db)
        statement = statement.where(Conversation.project_id == parsed_project_id)
        count_statement = count_statement.where(Conversation.project_id == parsed_project_id)

    if query:
        pattern = f"%{query.strip()}%"
        statement = statement.where(Conversation.title.ilike(pattern))
        count_statement = count_statement.where(Conversation.title.ilike(pattern))
    if date_from:
        statement = statement.where(Conversation.created_at >= date_from)
        count_statement = count_statement.where(Conversation.created_at >= date_from)
    if date_to:
        statement = statement.where(Conversation.created_at <= date_to)
        count_statement = count_statement.where(Conversation.created_at <= date_to)

    total = (await db.execute(count_statement)).scalar_one()
    result = await db.execute(statement.order_by(Conversation.updated_at.desc()).offset(offset).limit(limit))
    return {
        "message": "Conversations listed.",
        "data": {
            "workspace_id": str(workspace_id),
            "items": [_serialize_conversation_summary(item) for item in result.scalars().all()],
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID,
    workspace_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    conversation = await _get_conversation(conversation_id, workspace_id, db, with_messages=True)
    return {"message": "Conversation detail.", "data": _serialize_conversation(conversation, conversation.messages)}


@router.post("/{conversation_id}/messages", status_code=status.HTTP_202_ACCEPTED)
async def create_message(
    conversation_id: uuid.UUID,
    request: MessageCreate,
    background_tasks: BackgroundTasks,
    workspace_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    conversation = await _get_conversation(conversation_id, workspace_id, db)
    user_message = ConversationMessage(
        conversation_id=conversation.id,
        role="user",
        status="complete",
        content=request.content,
        metadata_=request.metadata,
    )
    assistant_message = ConversationMessage(
        conversation_id=conversation.id,
        role="assistant",
        status="generating",
        content="",
        metadata_={"mode": request.mode or conversation.mode},
    )
    if conversation.title == "New conversation":
        conversation.title = _title_from_message(request.content)
    conversation.updated_at = datetime.now(timezone.utc)
    db.add_all([user_message, assistant_message])
    await db.commit()
    await db.refresh(conversation)
    await db.refresh(user_message)
    await db.refresh(assistant_message)

    background_tasks.add_task(
        _generate_assistant_message,
        conversation.id,
        assistant_message.id,
        request.content,
        request.mode or conversation.mode,
        request.k,
        request.filters,
        request.project_ids,
    )
    messages = [user_message, assistant_message]
    return {"message": "Conversation message queued.", "data": _serialize_conversation(conversation, messages)}


@router.patch("/{conversation_id}")
async def update_conversation(
    conversation_id: uuid.UUID,
    request: ConversationUpdate,
    workspace_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    conversation = await _get_conversation(conversation_id, workspace_id, db)
    if request.title is not None:
        conversation.title = request.title
    if request.status is not None:
        conversation.status = request.status
    if request.context is not None:
        conversation.context = request.context
    if request.metadata is not None:
        conversation.metadata_ = request.metadata
    conversation.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(conversation)
    return {"message": "Conversation updated.", "data": _serialize_conversation(conversation, [])}


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: uuid.UUID,
    workspace_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    conversation = await _get_conversation(conversation_id, workspace_id, db)
    await db.execute(delete(Conversation).where(Conversation.id == conversation.id, Conversation.workspace_id == workspace_id))
    await db.commit()
    return {"message": "Conversation deleted.", "data": {"id": str(conversation_id), "workspace_id": str(workspace_id)}}


async def _generate_assistant_message(
    conversation_id: uuid.UUID,
    assistant_message_id: uuid.UUID,
    user_question: str,
    mode: str,
    k: int,
    filters: dict[str, Any],
    project_ids: list[uuid.UUID],
) -> None:
    async with AsyncSessionLocal() as db:
        conversation = await db.get(Conversation, conversation_id)
        assistant_message = await db.get(ConversationMessage, assistant_message_id)
        if not conversation or not assistant_message:
            return
        try:
            service = RAGService(db, get_embedding_provider(), get_llm_provider())
            if mode == "comparative":
                selected_project_ids = project_ids or ([conversation.project_id] if conversation.project_id else [])
                if not selected_project_ids:
                    raise ValueError("Comparative conversations require at least one project.")
                response = await service.comparative_query(user_question, selected_project_ids, k)
            else:
                if conversation.project_id is None:
                    raise ValueError("This conversation is not attached to a project.")
                response = await service.query(user_question, conversation.project_id, mode, k, filters)
            payload = response.model_dump(mode="json")
            assistant_message.content = response.answer
            assistant_message.status = "complete"
            assistant_message.citations = payload["citations"]
            assistant_message.retrieved_chunks = payload["retrieved_chunks"]
            assistant_message.graph_paths = payload["graph_paths"]
            assistant_message.confidence = response.confidence
            assistant_message.metadata_ = {
                **assistant_message.metadata_,
                "mode": response.mode,
                "confidence_rationale": response.confidence_rationale,
            }
        except Exception as error:  # noqa: BLE001 - persisted failure state is part of the user-facing workflow.
            assistant_message.status = "failed"
            assistant_message.content = "The assistant response could not be generated."
            assistant_message.metadata_ = {**assistant_message.metadata_, "error": str(error)}
        conversation.updated_at = datetime.now(timezone.utc)
        assistant_message.updated_at = datetime.now(timezone.utc)
        await db.commit()


async def _ensure_workspace(workspace_id: uuid.UUID, db: AsyncSession) -> Workspace:
    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail=f"Workspace not found: {workspace_id}")
    return workspace


async def _ensure_project_in_workspace(workspace_id: uuid.UUID, project_id: uuid.UUID, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project not found in workspace: {project_id}")
    return project


async def _get_conversation(
    conversation_id: uuid.UUID,
    workspace_id: uuid.UUID,
    db: AsyncSession,
    *,
    with_messages: bool = False,
) -> Conversation:
    statement = select(Conversation).where(Conversation.id == conversation_id, Conversation.workspace_id == workspace_id)
    if with_messages:
        statement = statement.options(selectinload(Conversation.messages))
    result = await db.execute(statement)
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail=f"Conversation not found in workspace: {conversation_id}")
    if with_messages:
        conversation.messages.sort(key=lambda message: message.created_at or datetime.min.replace(tzinfo=timezone.utc))
    return conversation


def _serialize_conversation(conversation: Conversation, messages: list[ConversationMessage]) -> dict[str, object]:
    return {
        **_serialize_conversation_summary(conversation),
        "messages": [_serialize_message(message) for message in messages],
    }


def _serialize_conversation_summary(conversation: Conversation) -> dict[str, object]:
    return {
        "id": str(conversation.id),
        "workspace_id": str(conversation.workspace_id),
        "project_id": str(conversation.project_id) if conversation.project_id else None,
        "title": conversation.title,
        "mode": conversation.mode,
        "status": conversation.status,
        "context": conversation.context,
        "metadata": conversation.metadata_,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
    }


def _serialize_message(message: ConversationMessage) -> dict[str, object]:
    return {
        "id": str(message.id),
        "conversation_id": str(message.conversation_id),
        "role": message.role,
        "status": message.status,
        "content": message.content,
        "citations": message.citations,
        "retrieved_chunks": message.retrieved_chunks,
        "graph_paths": message.graph_paths,
        "tool_calls": message.tool_calls,
        "confidence": message.confidence,
        "metadata": message.metadata_,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "updated_at": message.updated_at.isoformat() if message.updated_at else None,
    }


def _parse_uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=f"Invalid {label}: {value}") from error


def _title_from_message(content: str) -> str:
    compact = " ".join(content.strip().split())
    return compact[:80] if compact else "New conversation"
