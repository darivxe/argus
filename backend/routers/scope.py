from fastapi import APIRouter, Depends, HTTPException
from aiosqlite import Connection
from ..core.database import get_db
from ..core.ids import generate_id
from ..core.timeline import log_event
from ..models.schemas import ScopeCreate

router = APIRouter(prefix="/investigations/{inv_id}/scope", tags=["scope"])

@router.get("/")
async def list_scope(inv_id: str, db: Connection = Depends(get_db)):
    async with db.execute(
        "SELECT * FROM scope WHERE investigation_id = ? ORDER BY type, value", (inv_id,)
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]
    return {
        "in_scope":     [r for r in rows if r["type"] == "in_scope"],
        "out_of_scope": [r for r in rows if r["type"] == "out_of_scope"],
        "rules":        [r for r in rows if r["type"] == "rule"],
        "rewards":      [r for r in rows if r["type"] == "reward"],
    }

@router.post("/", status_code=201)
async def create_scope(inv_id: str, body: ScopeCreate, db: Connection = Depends(get_db)):
    async with db.execute("SELECT id FROM investigations WHERE id = ?", (inv_id,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Investigation not found")
    sid = generate_id()
    await db.execute(
        "INSERT INTO scope (id, investigation_id, type, value, notes) VALUES (?, ?, ?, ?, ?)",
        (sid, inv_id, body.type, body.value, body.notes)
    )
    await log_event(db, inv_id, 'scope_imported',
                    f"Scope entry added — [{body.type}] {body.value}",
                    {"scope_id": sid, "type": body.type})
    await db.commit()
    async with db.execute("SELECT * FROM scope WHERE id = ?", (sid,)) as cur:
        return dict(await cur.fetchone())

@router.delete("/{sid}", status_code=204)
async def delete_scope(inv_id: str, sid: str, db: Connection = Depends(get_db)):
    await db.execute("DELETE FROM scope WHERE id = ? AND investigation_id = ?", (sid, inv_id))
    await db.commit()
