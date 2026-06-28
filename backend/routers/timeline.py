from fastapi import APIRouter, Depends
from aiosqlite import Connection
from ..core.database import get_db

router = APIRouter(prefix="/investigations/{inv_id}/timeline", tags=["timeline"])

@router.get("/")
async def get_timeline(inv_id: str, db: Connection = Depends(get_db)):
    async with db.execute(
        "SELECT * FROM timeline WHERE investigation_id = ? ORDER BY created_at ASC", (inv_id,)
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]
