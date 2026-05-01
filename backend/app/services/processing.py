from uuid import UUID


async def enqueue_document_processing(document_id: UUID) -> dict[str, str]:
    return {"document_id": str(document_id), "status": "not_queued"}
