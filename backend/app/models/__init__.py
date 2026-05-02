import importlib

from app.models.document import Chunk, ChunkEmbedding, Document, DocumentStatus
from app.models.conversation import Conversation, ConversationMessage
from app.models.graph import CrossProjectLink, GraphEdge, GraphNode
from app.models.jobs import ChunkCluster, Cluster, ProcessingJob, ProcessingJobStatus, ResearchNote
from app.models.knowledge import Claim, Concept, Entity
from app.models.workspace import Project, Workspace

_global_models = importlib.import_module("app.models.global")
GlobalCanonicalEntity = _global_models.GlobalCanonicalEntity
GlobalCanonicalConcept = _global_models.GlobalCanonicalConcept

__all__ = [
    "Chunk",
    "ChunkCluster",
    "ChunkEmbedding",
    "Claim",
    "Cluster",
    "Concept",
    "Conversation",
    "ConversationMessage",
    "CrossProjectLink",
    "Document",
    "DocumentStatus",
    "Entity",
    "GlobalCanonicalConcept",
    "GlobalCanonicalEntity",
    "GraphEdge",
    "GraphNode",
    "ProcessingJob",
    "ProcessingJobStatus",
    "Project",
    "ResearchNote",
    "Workspace",
]
