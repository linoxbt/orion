"""Where negotiations live.

Supabase when it is configured, the local SQLite file otherwise. The fallback
is not decoration: it keeps the app working before the Supabase key is set, and
keeps the test suite off the network.

SQLite was always the interim - a single file on a single Railway volume, no
backups, gone with the volume. It also had no notion of an owner, which is why
every signed-in user could list every negotiation in the system.

Original docstring follows.

SQLite-backed NegotiationSession store.

Replaces the earlier plain in-memory dict, whose most immediate problem was
that a backend restart wiped every session. Firestore (architecture doc
Section 2/6) is the real target once a GCP project exists - this is the
interim fix, not the final one.

Every function here is async (aiosqlite) and opens a short-lived connection
per call; fine at this app's scale, and simpler to reason about than holding
one connection open for the process lifetime.
"""

import logging
import pathlib

import aiosqlite

from app.config import settings
from app.models import NegotiationSession
from app.services import supabase_store

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS negotiations (
    task_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


async def _migrate_sqlite_to_supabase() -> None:
    """Carry any local rows over the first time Supabase is switched on.

    Without this the cutover looked like data loss: every negotiation created
    while the app was on SQLite simply stopped existing the moment the key was
    set. Rows are upserted by task_id, so running twice is harmless.
    """
    path = pathlib.Path(settings.database_path)
    if not path.exists():
        return

    try:
        async with aiosqlite.connect(settings.database_path) as db:
            cursor = await db.execute("SELECT data FROM negotiations")
            rows = await cursor.fetchall()
    except aiosqlite.Error:
        # No table, or an unreadable file - nothing to carry over.
        return

    if not rows:
        return

    migrated = 0
    for row in rows:
        try:
            session = NegotiationSession.model_validate_json(row[0])
            await supabase_store.save_session(session)
            migrated += 1
        except Exception as exc:  # noqa: BLE001 - one bad row must not stop the rest
            logger.warning("Could not migrate a local negotiation: %s", exc)

    logger.info("Migrated %s/%s local negotiations into Supabase", migrated, len(rows))
    # Rename rather than delete: if the migration was wrong, the data is still
    # on disk to look at.
    path.rename(path.with_suffix(".db.migrated"))


async def init_db() -> None:
    if supabase_store.is_configured():
        logger.info("Using Supabase for persistence")
        await _migrate_sqlite_to_supabase()
        return
    logger.warning(
        "SUPABASE_URL/SUPABASE_SERVICE_KEY unset - falling back to local SQLite, "
        "which has no backups and no user scoping"
    )
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(_CREATE_TABLE)
        await db.commit()


async def save_session(session: NegotiationSession) -> None:
    if supabase_store.is_configured():
        return await supabase_store.save_session(session)
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "INSERT INTO negotiations (task_id, data) VALUES (?, ?) "
            "ON CONFLICT(task_id) DO UPDATE SET data = excluded.data",
            (session.task_id, session.model_dump_json()),
        )
        await db.commit()


async def get_session(task_id: str) -> NegotiationSession | None:
    if supabase_store.is_configured():
        return await supabase_store.get_session(task_id)
    async with aiosqlite.connect(settings.database_path) as db:
        cursor = await db.execute("SELECT data FROM negotiations WHERE task_id = ?", (task_id,))
        row = await cursor.fetchone()
    if row is None:
        return None
    return NegotiationSession.model_validate_json(row[0])


async def list_sessions(
    user_id: str | None = None, *, limit: int = 100, offset: int = 0
) -> list[NegotiationSession]:
    """Scoped to one user unless called deliberately without one.

    user_id=None returns everything and exists only for the server-side
    renewals sweep; it is never reachable from a browser.
    """
    if supabase_store.is_configured():
        return await supabase_store.list_sessions(user_id, limit=limit, offset=offset)

    async with aiosqlite.connect(settings.database_path) as db:
        cursor = await db.execute(
            "SELECT data FROM negotiations ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
    sessions = [NegotiationSession.model_validate_json(row[0]) for row in rows]
    if user_id is None:
        return sessions
    # The SQLite table predates user scoping, so filter in Python rather than
    # migrating a store that is on its way out.
    return [s for s in sessions if s.user_id == user_id]
