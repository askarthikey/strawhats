from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

client: AsyncIOMotorClient = None
db = None


async def connect_db():
    global client, db
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]
    await create_indexes()
    return db


async def close_db():
    global client
    if client:
        client.close()


async def create_indexes():
    """Create MongoDB indexes for performance and deduplication."""
    # Users: unique email
    await db.users.create_index("email", unique=True)

    # Papers: drop old global DOI index if it exists, replace with per-workspace compound
    try:
        index_info = await db.papers.index_information()
        if "doi_1" in index_info:
            await db.papers.drop_index("doi_1")
    except Exception:
        pass
    # Compound unique DOI per workspace (sparse so papers without DOI are allowed)
    await db.papers.create_index(
        [("doi", 1), ("workspace_id", 1)],
        unique=True,
        sparse=True,
        name="doi_workspace_unique",
    )
    # Text index for hybrid search
    await db.papers.create_index([("title", "text"), ("abstract", "text")])
    # Workspace filter
    await db.papers.create_index("workspace_id")

    # Chunks: compound index
    await db.chunks.create_index([("paper_id", 1), ("chunk_index", 1)], unique=True)
    await db.chunks.create_index("paper_id")

    # Chat logs
    await db.chat_logs.create_index([("workspace_id", 1), ("created_at", -1)])
    await db.chat_logs.create_index("user_id")

    # Drafts
    await db.drafts.create_index("workspace_id")
    await db.drafts.create_index("author_id")

    # Draft versions
    await db.draft_versions.create_index([("draft_id", 1), ("created_at", -1)])

    # Workspaces
    await db.workspaces.create_index("owner_id")
    await db.workspaces.create_index("members.user_id")


def get_db():
    return db
