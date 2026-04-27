# app/core/database.py
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.core.config import settings

_client: AsyncIOMotorClient = None


async def connect_db():
    global _client
    _client = AsyncIOMotorClient(settings.MONGO_URI)
    from app.models.user         import User
    from app.models.post         import Post
    from app.models.comment      import Comment
    from app.models.like         import Like
    from app.models.follow       import Follow
    from app.models.event        import Event
    from app.models.notification import Notification

    await init_beanie(
        database=_client[settings.DB_NAME],
        document_models=[User, Post, Comment, Like, Follow, Event, Notification],
    )
    print(f"✅  MongoDB connected  →  {settings.DB_NAME}")


async def close_db():
    global _client
    if _client:
        _client.close()
        print("MongoDB connection closed")
