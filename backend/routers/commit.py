"""
/commit command handler.
Terminal intercepts lines starting with /commit and POSTs here.
Single transaction per commit — one db.commit() at the end.
"""
from fastapi import APIRouter, Depends, HTTPException
from aiosqlite import Connection
from ..core.database import get_db
from ..core.ids import generate_id
from ..core.timeline import log_event
from ..models.schemas import CommitPayload

router = APIRouter(prefix="/commit", tags=["commit"])

TECHNOLOGY_ALIASES = {
    "cloudflare": "cdn", "fastly": "cdn", "akamai": "cdn",
    "nginx": "service", "apache": "service",
    "wordpress": "cms", "drupal": "cms", "joomla": "cms",
    "aws": "cloud_provider", "gcp": "cloud_provider", "azure": "cloud_provider",
    "react": "framework", "django": "framework", "rails": "framework", "laravel": "framework",
    "next.js": "framework", "nuxt": "framework", "express": "framework",
    "python": "language", "php": "language", "javascript": "language",
    "ruby": "language", "go": "language", "java": "language",
}

@router.post("/")
async def handle_commit(body: CommitPayload, db: Connection = Depends(get_db)):
    async with db.execute("SELECT id FROM investigations WHERE id = ?", (body.investigation_id,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Investigation not found")

    inv_id = body.investigation_id
    result = {}

    if body.command == "finding":
        fid = generate_id()
        severity = body.severity or "medium"
        await db.execute(
            "INSERT INTO findings (id, investigation_id, title, severity) VALUES (?, ?, ?, ?)",
            (fid, inv_id, body.value, severity)
        )
        await log_event(db, inv_id, 'finding_committed',
                        f"Finding committed — {body.value} ({severity})",
                        {"finding_id": fid, "severity": severity})
        result = {"committed": "finding", "id": fid, "title": body.value, "severity": severity}

    elif body.command == "note":
        nid = generate_id()
        await db.execute(
            "INSERT INTO notes (id, investigation_id, content, source) VALUES (?, ?, ?, 'committed')",
            (nid, inv_id, body.value)
        )
        await log_event(db, inv_id, 'note_committed',
                        f"Note committed — {body.value[:60]}",
                        {"note_id": nid})
        result = {"committed": "note", "id": nid}

    elif body.command == "asset":
        asset_type = body.asset_type or "domain"
        aid = generate_id()
        await db.execute(
            "INSERT INTO assets (id, investigation_id, type, value, source) VALUES (?, ?, ?, ?, 'committed')",
            (aid, inv_id, asset_type, body.value)
        )
        await log_event(db, inv_id, 'asset_committed',
                        f"Asset committed — [{asset_type}] {body.value}",
                        {"asset_id": aid, "type": asset_type})
        result = {"committed": "asset", "id": aid, "type": asset_type, "value": body.value}

    elif body.command == "endpoint":
        aid = generate_id()
        await db.execute(
            "INSERT INTO assets (id, investigation_id, type, value, source) VALUES (?, ?, 'endpoint', ?, 'committed')",
            (aid, inv_id, body.value)
        )
        await log_event(db, inv_id, 'endpoint_committed',
                        f"Endpoint committed — {body.value}",
                        {"asset_id": aid})
        result = {"committed": "endpoint", "id": aid, "value": body.value}

    elif body.command == "technology":
        lowered = body.value.lower().split()[0]  # strip version for alias lookup
        asset_type = TECHNOLOGY_ALIASES.get(lowered, "framework")
        aid = generate_id()
        await db.execute(
            "INSERT INTO assets (id, investigation_id, type, value, source) VALUES (?, ?, ?, ?, 'committed')",
            (aid, inv_id, asset_type, body.value)  # store full value e.g. "Next.js 15"
        )
        await log_event(db, inv_id, 'technology_committed',
                        f"Technology committed — [{asset_type}] {body.value}",
                        {"asset_id": aid, "type": asset_type})
        result = {"committed": "technology", "id": aid, "type": asset_type, "value": body.value}

    else:
        raise HTTPException(400, f"Unknown commit command: {body.command}")

    # single commit for the entire operation
    await db.commit()
    return result
