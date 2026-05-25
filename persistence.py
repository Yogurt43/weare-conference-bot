# persistence.py
"""Supabase-backed persistence for PTB ConversationHandler state.

Only conversation state is persisted — user_data / chat_data / bot_data
are left in-memory because all durable state lives in Supabase directly.

Conversation state is stored as a single JSON blob per conversation name
in the bot_settings table under the key 'conv_state_<name>'.

Format: {"[chat_id, user_id]": <state_int>}

A local in-memory cache avoids redundant reads between get and update
within the same process lifetime.
"""
import json
import logging
from collections import defaultdict
from typing import Optional

from telegram.ext import BasePersistence, PersistenceInput
from telegram.ext._utils.types import CDCData, ConversationDict

import db

logger = logging.getLogger(__name__)

_PREFIX = 'conv_state_'


class SupabasePersistence(BasePersistence):
    """Persists ConversationHandler state to Supabase bot_settings."""

    def __init__(self) -> None:
        # Only persist conversations; skip user/chat/bot/callback data
        super().__init__(store_data=PersistenceInput(
            bot_data=False,
            chat_data=False,
            user_data=False,
            callback_data=False,
        ))
        self._cache: dict[str, ConversationDict] = {}

    # ── Conversations (the only thing we actually persist) ────────────────────

    async def get_conversations(self, name: str) -> ConversationDict:
        raw = db.get_setting(f'{_PREFIX}{name}')
        if not raw:
            self._cache[name] = {}
            return {}
        try:
            data: dict = json.loads(raw)
            result: ConversationDict = {
                tuple(json.loads(k)): v
                for k, v in data.items()
            }
            self._cache[name] = result
            return result
        except Exception:
            logger.exception('Failed to load conversation state for %s', name)
            self._cache[name] = {}
            return {}

    async def update_conversation(
        self, name: str, key: tuple, new_state: Optional[object]
    ) -> None:
        convs = dict(self._cache.get(name, {}))
        if new_state is None:
            convs.pop(key, None)
        else:
            convs[key] = new_state
        self._cache[name] = convs
        try:
            serializable = {
                json.dumps(list(k)): v
                for k, v in convs.items()
                if v is not None
            }
            db.set_setting(f'{_PREFIX}{name}', json.dumps(serializable))
        except Exception:
            logger.exception(
                'Failed to save conversation state for %s key=%s state=%s',
                name, key, new_state,
            )

    # ── Stubs — in-memory only, we don't persist these ────────────────────────

    async def get_user_data(self) -> dict:
        return defaultdict(dict)

    async def update_user_data(self, user_id: int, data: dict) -> None:
        pass

    async def get_chat_data(self) -> dict:
        return defaultdict(dict)

    async def update_chat_data(self, chat_id: int, data: dict) -> None:
        pass

    async def get_bot_data(self) -> dict:
        return {}

    async def update_bot_data(self, data: dict) -> None:
        pass

    async def get_callback_data(self) -> CDCData | None:
        return None

    async def update_callback_data(self, data: CDCData) -> None:
        pass

    async def drop_chat_data(self, chat_id: int) -> None:
        pass

    async def drop_user_data(self, user_id: int) -> None:
        pass

    async def refresh_user_data(self, user_id: int, user_data: dict) -> None:
        pass

    async def refresh_chat_data(self, chat_id: int, chat_data: dict) -> None:
        pass

    async def refresh_bot_data(self, bot_data: dict) -> None:
        pass

    async def flush(self) -> None:
        pass
