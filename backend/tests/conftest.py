import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://example@example/example")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
os.environ.setdefault("ANTHROPIC_API_KEY", "dev")
os.environ.setdefault("OPENAI_API_KEY", "dev")
os.environ.setdefault("EMBEDDING_PROVIDER", "local")
os.environ.setdefault("EXTRACTION_PROVIDER", "local")
os.environ.setdefault("LLM_PROVIDER", "local")
os.environ.setdefault("DRAMATIQ_DEV_MODE", "true")
