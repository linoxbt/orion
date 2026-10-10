"""The Supabase cutover preserves real work without importing demo rows."""

import asyncio

import aiosqlite
import pytest

from app import store
from app.services.demo_seed import build_samples


@pytest.mark.parametrize("fail_save", [False, True])
def test_cutover_skips_samples_and_retries_failed_real_rows(tmp_path, monkeypatch, fail_save):
    path = tmp_path / "orion.db"
    sample = build_samples("owner")[0]
    real = sample.model_copy(update={"task_id": "real-task", "is_sample": False})

    async def setup():
        async with aiosqlite.connect(path) as db:
            await db.execute(store._CREATE_TABLE)
            for session in (sample, real):
                await db.execute(
                    "INSERT INTO negotiations (task_id, data) VALUES (?, ?)",
                    (session.task_id, session.model_dump_json()),
                )
            await db.commit()

    asyncio.run(setup())
    monkeypatch.setattr(store.settings, "database_path", str(path))
    saved = []

    async def save(session):
        saved.append(session.task_id)
        if fail_save:
            raise RuntimeError("temporary outage")

    monkeypatch.setattr(store.supabase_store, "save_session", save)
    asyncio.run(store._migrate_sqlite_to_supabase())

    assert saved == ["real-task"]
    assert path.exists() is fail_save
    assert path.with_suffix(".db.migrated").exists() is (not fail_save)
