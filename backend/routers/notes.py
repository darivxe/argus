from fastapi import APIRouter, Depends, HTTPException
from aiosqlite import Connection
from ..core.database import get_db
from ..core.ids import generate_id
from ..core.timeline import log_event
from ..models.schemas import NoteCreate

router = APIRouter(prefix="/investigations/{inv_id}/notes", tags=["notes"])

@router.get("/")
async def list_notes(inv_id: str, db: Connection = Depends(get_db)):
    async with db.execute(
        "SELECT * FROM notes WHERE investigation_id = ? ORDER BY created_at DESC", (inv_id,)
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]

@router.post("/", status_code=201)
async def create_note(inv_id: str, body: NoteCreate, db: Connection = Depends(get_db)):
    async with db.execute("SELECT id FROM investigations WHERE id = ?", (inv_id,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Investigation not found")
    nid = generate_id()
    await db.execute(
        "INSERT INTO notes (id, investigation_id, content, source) VALUES (?, ?, ?, ?)",
        (nid, inv_id, body.content, body.source)
    )
    await log_event(db, inv_id, 'note_committed',
                    f"Note added — {body.content[:60]}{'...' if len(body.content) > 60 else ''}",
                    {"note_id": nid, "source": body.source})
    await db.commit()
    async with db.execute("SELECT * FROM notes WHERE id = ?", (nid,)) as cur:
        return dict(await cur.fetchone())

@router.delete("/{nid}", status_code=204)
async def delete_note(inv_id: str, nid: str, db: Connection = Depends(get_db)):
    await db.execute("DELETE FROM notes WHERE id = ? AND investigation_id = ?", (nid, inv_id))
    await db.commit()
