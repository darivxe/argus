from fastapi import APIRouter, Depends
from aiosqlite import Connection
from ..core.database import get_db
from ..models.schemas import SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("/")
async def get_settings(db: Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM settings WHERE id = 1") as cur:
        row = await cur.fetchone()
    data = dict(row)
    # never return the raw API key
    if data.get("anthropic_api_key"):
        data["anthropic_api_key"] = "sk-***"
    return data

@router.patch("/")
async def update_settings(body: SettingsUpdate, db: Connection = Depends(get_db)):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return {"updated": False}
    fields = ", ".join(f"{k} = ?" for k in updates)
    await db.execute(
        f"UPDATE settings SET {fields}, updated_at = datetime('now') WHERE id = 1",
        (*updates.values(),)
    )
    await db.commit()
    return {"updated": True, "fields": list(updates.keys())}
