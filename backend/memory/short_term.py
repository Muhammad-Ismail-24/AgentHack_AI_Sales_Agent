"""Short-term memory — the live state of a pipeline run, held in Redis.

Everything here is scoped to a session_id and expires after two hours. It is
deliberately throwaway: anything worth keeping goes to the database through
memory/long_term.py.
"""

from typing import Any

from config.settings import settings
from utils.cache import cache_delete, cache_get, cache_set
from utils.logger import get_logger

log = get_logger(__name__)

TTL = settings.PIPELINE_STATE_TTL_SECONDS


class ShortTermMemory:
    """Redis-backed working memory for one pipeline run."""

    # ── key helpers ──────────────────────────────────────────────────

    @staticmethod
    def _state_key(session_id: str) -> str:
        return f"pipeline:{session_id}"

    @staticmethod
    def _stage_key(session_id: str) -> str:
        return f"stage:{session_id}"

    @staticmethod
    def _company_key(session_id: str) -> str:
        return f"company:{session_id}"

    @staticmethod
    def _icp_key(session_id: str) -> str:
        return f"icp:{session_id}"

    # ── pipeline state ───────────────────────────────────────────────

    def set_pipeline_state(self, session_id: str, state: dict) -> None:
        cache_set(self._state_key(session_id), state, ttl=TTL)

    def get_pipeline_state(self, session_id: str) -> dict | None:
        return cache_get(self._state_key(session_id))

    def update_pipeline_state(self, session_id: str, **updates: Any) -> dict:
        """Merge keys into the stored state, creating it if absent."""
        state = self.get_pipeline_state(session_id) or {}
        state.update(updates)
        self.set_pipeline_state(session_id, state)
        return state

    # ── current stage ────────────────────────────────────────────────

    def set_pipeline_stage(self, session_id: str, stage: str) -> None:
        cache_set(self._stage_key(session_id), stage, ttl=TTL)
        log.info("session %s -> stage %s", session_id, stage)

    def get_pipeline_stage(self, session_id: str) -> str | None:
        return cache_get(self._stage_key(session_id))

    # ── company knowledge (from RAG ingest) ──────────────────────────

    def set_company(self, session_id: str, company: dict) -> None:
        cache_set(self._company_key(session_id), company, ttl=TTL)

    def get_company(self, session_id: str) -> dict | None:
        return cache_get(self._company_key(session_id))

    # ── ICP (from the onboarding form) ───────────────────────────────

    def set_icp(self, session_id: str, icp: dict) -> None:
        cache_set(self._icp_key(session_id), icp, ttl=TTL)

    def get_icp(self, session_id: str) -> dict | None:
        return cache_get(self._icp_key(session_id))

    # ── teardown ─────────────────────────────────────────────────────

    def clear_session(self, session_id: str) -> None:
        cache_delete(
            self._state_key(session_id),
            self._stage_key(session_id),
            self._company_key(session_id),
            self._icp_key(session_id),
        )
        log.info("cleared session %s", session_id)


short_term_memory = ShortTermMemory()
