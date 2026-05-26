from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo.collection import Collection

from app.config import Settings, get_settings
from app.db.mongo import get_database, serialize_mongo


class ChatContextRepository:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.db = get_database()

    @property
    def sessions(self) -> Collection:
        return self.db[self.settings.chat_sessions_collection]

    @property
    def messages(self) -> Collection:
        return self.db[self.settings.chat_messages_collection]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        doc = self.sessions.find_one({"_id": session_id})
        return serialize_mongo(doc) if doc else None

    def ensure_session(self, session_id: str, user_id: str | None) -> dict[str, Any]:
        now = now_utc()
        self.sessions.update_one(
            {"_id": session_id},
            {
                "$set": {"user_id": user_id, "updated_at": now},
                "$setOnInsert": {"created_at": now, "memory": {}},
            },
            upsert=True,
        )
        return self.get_session(session_id) or {"_id": session_id, "user_id": user_id, "memory": {}}

    def update_session_memory(self, session_id: str, updates: dict[str, Any]) -> None:
        payload = {f"memory.{key}": value for key, value in updates.items()}
        payload["updated_at"] = now_utc()
        self.sessions.update_one({"_id": session_id}, {"$set": payload}, upsert=True)

    def append_message(self, session_id: str, user_id: str | None, role: str, content: str, extra: dict[str, Any] | None = None) -> None:
        doc = {
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "extra": extra or {},
            "created_at": now_utc(),
        }
        self.messages.insert_one(doc)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
