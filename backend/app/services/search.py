from uuid import UUID


async def run_project_scoped_search(project_id: UUID, query: str) -> dict[str, object]:
    return {"project_id": str(project_id), "query": query, "chunks": []}
