from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from aiosqlite import Connection
from ..core.database import get_db
from ..core.ids import generate_id
from ..core.timeline import log_event
from ..models.schemas import ReportCreate, ReportUpdate

router = APIRouter(prefix="/investigations/{inv_id}/reports", tags=["reports"])

@router.get("/")
async def list_reports(inv_id: str, db: Connection = Depends(get_db)):
    async with db.execute(
        "SELECT * FROM reports WHERE investigation_id = ? ORDER BY created_at DESC", (inv_id,)
    ) as cur:
        return [dict(r) for r in await cur.fetchall()]

@router.post("/", status_code=201)
async def create_report(inv_id: str, body: ReportCreate, db: Connection = Depends(get_db)):
    async with db.execute("SELECT id FROM investigations WHERE id = ?", (inv_id,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Investigation not found")
    rid = generate_id()
    await db.execute(
        "INSERT INTO reports (id, investigation_id, title, author, content) VALUES (?, ?, ?, ?, ?)",
        (rid, inv_id, body.title, body.author, body.content)
    )
    await log_event(db, inv_id, 'report_created',
                    f"Report created — {body.title} (by {body.author})",
                    {"report_id": rid, "author": body.author})
    await db.commit()
    async with db.execute("SELECT * FROM reports WHERE id = ?", (rid,)) as cur:
        return dict(await cur.fetchone())

@router.patch("/{rid}")
async def update_report(inv_id: str, rid: str, body: ReportUpdate, db: Connection = Depends(get_db)):
    async with db.execute(
        "SELECT id FROM reports WHERE id = ? AND investigation_id = ?", (rid, inv_id)
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Report not found")
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "Nothing to update")
    fields = ", ".join(f"{k} = ?" for k in updates)
    await db.execute(f"UPDATE reports SET {fields} WHERE id = ?", (*updates.values(), rid))
    await db.commit()
    async with db.execute("SELECT * FROM reports WHERE id = ?", (rid,)) as cur:
        return dict(await cur.fetchone())

@router.get("/{rid}/export", response_class=PlainTextResponse)
async def export_report(inv_id: str, rid: str, db: Connection = Depends(get_db)):
    async with db.execute(
        "SELECT * FROM reports WHERE id = ? AND investigation_id = ?", (rid, inv_id)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Report not found")
    return row["content"]
