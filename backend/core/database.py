import aiosqlite
import os
from pathlib import Path

DB_PATH = Path(os.getenv("ARGUS_DB", str(Path.home() / ".argus" / "argus.db")))

async def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        yield db

async def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    schema_path = Path(__file__).parent.parent.parent / "schema.sql"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        with open(schema_path) as f:
            await db.executescript(f.read())
        await db.commit()
