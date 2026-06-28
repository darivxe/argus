from fastapi import APIRouter, Depends, HTTPException
from aiosqlite import Connection
from ..core.database import get_db
from ..core.ids import generate_investigation_id
from ..core.timeline import log_event
from ..models.schemas import InvestigationCreate, InvestigationUpdate

router = APIRouter(prefix="/investigations", tags=["investigations"])

# explicit whitelist — never trust field names from user input directly
ALLOWED_UPDATE_FIELDS = {"status", "description", "program", "platform"}

@router.get("/")
async def list_investigations(db: Connection = Depends(get_db)):
    async with db.execute(
        """SELECT i.*,
                  COUNT(DISTINCT f.id) as finding_count
           FROM investigations i
           LEFT JOIN findings f ON f.investigation_id = i.id
           GROUP BY i.id
           ORDER BY i.last_activity DESC"""
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]

@router.post("/", status_code=201)
async def create_investigation(body: InvestigationCreate, db: Connection = Depends(get_db)):
    inv_id = generate_investigation_id()
    await db.execute(
        "INSERT INTO investigations (id, target, program, platform, description) VALUES (?, ?, ?, ?, ?)",
        (inv_id, body.target, body.program, body.platform, body.description)
    )
    await db.execute(
        "INSERT INTO session_summary (investigation_id, content) VALUES (?, '')", (inv_id,)
    )
    await log_event(db, inv_id, 'investigation_created',
                    f"Investigation created for {body.target}",
                    {"target": body.target, "program": body.program})
    await db.commit()
    async with db.execute("SELECT * FROM investigations WHERE id = ?", (inv_id,)) as cur:
        return dict(await cur.fetchone())

@router.get("/{inv_id}")
async def get_investigation(inv_id: str, db: Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM investigations WHERE id = ?", (inv_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Investigation not found")
    return dict(row)

@router.patch("/{inv_id}")
async def update_investigation(inv_id: str, body: InvestigationUpdate, db: Connection = Depends(get_db)):
    async with db.execute("SELECT id FROM investigations WHERE id = ?", (inv_id,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Investigation not found")

    updates = {
        k: v for k, v in body.model_dump(exclude_none=True).items()
        if k in ALLOWED_UPDATE_FIELDS  # explicit whitelist
    }
    if not updates:
        raise HTTPException(400, "Nothing to update")

    fields = ", ".join(f"{k} = ?" for k in updates)
    await db.execute(
        f"UPDATE investigations SET {fields} WHERE id = ?",
        (*updates.values(), inv_id)
    )
    if "status" in updates:
        await log_event(db, inv_id, 'investigation_status_changed',
                        f"Status changed to {updates['status']}",
                        {"status": updates["status"]})
    await db.commit()
    async with db.execute("SELECT * FROM investigations WHERE id = ?", (inv_id,)) as cur:
        return dict(await cur.fetchone())

@router.delete("/{inv_id}", status_code=204)
async def delete_investigation(inv_id: str, db: Connection = Depends(get_db)):
    await db.execute("DELETE FROM investigations WHERE id = ?", (inv_id,))
    await db.commit()
