from fastapi import APIRouter, Depends, HTTPException
from aiosqlite import Connection
from ..core.database import get_db
from ..core.ids import generate_id
from ..core.timeline import log_event
from ..models.schemas import FindingCreate, FindingUpdate

router = APIRouter(prefix="/investigations/{inv_id}/findings", tags=["findings"])

async def _check_inv(inv_id, db):
    async with db.execute("SELECT id FROM investigations WHERE id = ?", (inv_id,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Investigation not found")

@router.get("/")
async def list_findings(inv_id: str, db: Connection = Depends(get_db)):
    await _check_inv(inv_id, db)
    async with db.execute(
        "SELECT * FROM findings WHERE investigation_id = ? ORDER BY created_at DESC",
        (inv_id,)
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]

@router.post("/", status_code=201)
async def create_finding(inv_id: str, body: FindingCreate, db: Connection = Depends(get_db)):
    await _check_inv(inv_id, db)
    fid = generate_id()
    await db.execute(
        """INSERT INTO findings (id, investigation_id, title, description,
                                 severity, reproduction_steps, remediation)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (fid, inv_id, body.title, body.description,
         body.severity, body.reproduction_steps, body.remediation)
    )
    await log_event(db, inv_id, 'finding_committed',
                    f"Finding committed — {body.title} ({body.severity})",
                    {"finding_id": fid, "severity": body.severity})
    await db.commit()
    async with db.execute("SELECT * FROM findings WHERE id = ?", (fid,)) as cur:
        return dict(await cur.fetchone())

@router.get("/{fid}")
async def get_finding(inv_id: str, fid: str, db: Connection = Depends(get_db)):
    async with db.execute(
        "SELECT * FROM findings WHERE id = ? AND investigation_id = ?", (fid, inv_id)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Finding not found")
    return dict(row)

@router.patch("/{fid}")
async def update_finding(inv_id: str, fid: str, body: FindingUpdate, db: Connection = Depends(get_db)):
    async with db.execute(
        "SELECT * FROM findings WHERE id = ? AND investigation_id = ?", (fid, inv_id)
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Finding not found")
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "Nothing to update")
    fields = ", ".join(f"{k} = ?" for k in updates)
    await db.execute(f"UPDATE findings SET {fields} WHERE id = ?", (*updates.values(), fid))
    if "status" in updates:
        await log_event(db, inv_id, 'finding_status_changed',
                        f"Finding status changed to {updates['status']}",
                        {"finding_id": fid, "status": updates["status"]})
    await db.commit()
    async with db.execute("SELECT * FROM findings WHERE id = ?", (fid,)) as cur:
        return dict(await cur.fetchone())

@router.delete("/{fid}", status_code=204)
async def delete_finding(inv_id: str, fid: str, db: Connection = Depends(get_db)):
    await db.execute("DELETE FROM findings WHERE id = ? AND investigation_id = ?", (fid, inv_id))
    await db.commit()

@router.get("/{fid}/reviews")
async def list_reviews(inv_id: str, fid: str, db: Connection = Depends(get_db)):
    async with db.execute(
        "SELECT * FROM finding_reviews WHERE finding_id = ? ORDER BY created_at DESC", (fid,)
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]
