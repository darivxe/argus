from fastapi import APIRouter, Depends, HTTPException
from aiosqlite import Connection
from ..core.database import get_db
from ..core.ids import generate_id
from ..core.timeline import log_event
from ..models.schemas import AssetCreate, AssetStatusUpdate

router = APIRouter(prefix="/investigations/{inv_id}/assets", tags=["assets"])

# T-Intel groupings — UI uses these, not raw types
TINTEL_GROUPS = {
    "infrastructure": ["domain", "subdomain", "ip", "url", "port", "service"],
    "technology":     ["framework", "cdn", "waf", "cms", "cloud_provider", "language"],
    "recon":          ["endpoint", "parameter", "header"],
}

@router.get("/")
async def list_assets(inv_id: str, db: Connection = Depends(get_db)):
    async with db.execute(
        "SELECT * FROM assets WHERE investigation_id = ? ORDER BY type, value",
        (inv_id,)
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]
    # return grouped for T-Intel
    grouped = {"infrastructure": [], "technology": [], "recon": []}
    for row in rows:
        for group, types in TINTEL_GROUPS.items():
            if row["type"] in types:
                grouped[group].append(row)
    return {"grouped": grouped, "all": rows}

@router.post("/", status_code=201)
async def create_asset(inv_id: str, body: AssetCreate, db: Connection = Depends(get_db)):
    async with db.execute("SELECT id FROM investigations WHERE id = ?", (inv_id,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Investigation not found")
    aid = generate_id()
    await db.execute(
        """INSERT INTO assets (id, investigation_id, type, value, parent_id, notes, source)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (aid, inv_id, body.type, body.value, body.parent_id, body.notes, body.source)
    )
    await log_event(db, inv_id, 'asset_committed',
                    f"Asset committed — [{body.type}] {body.value}",
                    {"asset_id": aid, "type": body.type, "value": body.value})
    await db.commit()
    async with db.execute("SELECT * FROM assets WHERE id = ?", (aid,)) as cur:
        return dict(await cur.fetchone())

@router.patch("/{aid}/status")
async def update_asset_status(inv_id: str, aid: str, body: AssetStatusUpdate, db: Connection = Depends(get_db)):
    async with db.execute(
        "SELECT id FROM assets WHERE id = ? AND investigation_id = ?", (aid, inv_id)
    ) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Asset not found")
    await db.execute("UPDATE assets SET status = ? WHERE id = ?", (body.status, aid))
    await db.commit()
    async with db.execute("SELECT * FROM assets WHERE id = ?", (aid,)) as cur:
        return dict(await cur.fetchone())

@router.delete("/{aid}", status_code=204)
async def delete_asset(inv_id: str, aid: str, db: Connection = Depends(get_db)):
    await db.execute("DELETE FROM assets WHERE id = ? AND investigation_id = ?", (aid, inv_id))
    await db.commit()
