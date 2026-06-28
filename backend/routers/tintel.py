"""
T-Intel endpoint.
Single route that assembles the full target intelligence profile
from assets, scope, findings, notes, and timeline.
Frontend never needs to fetch 8 separate routes for the T-Intel tab.
"""
from fastapi import APIRouter, Depends, HTTPException
from aiosqlite import Connection
from ..core.database import get_db

router = APIRouter(prefix="/investigations", tags=["t-intel"])

TINTEL_GROUPS = {
    "infrastructure": ["domain", "subdomain", "ip", "url", "port", "service"],
    "technology":     ["framework", "cdn", "waf", "cms", "cloud_provider", "language"],
    "recon":          ["endpoint", "parameter", "header"],
}

@router.get("/{inv_id}/t-intel")
async def get_tintel(inv_id: str, db: Connection = Depends(get_db)):
    async with db.execute("SELECT * FROM investigations WHERE id = ?", (inv_id,)) as cur:
        inv = await cur.fetchone()
    if not inv:
        raise HTTPException(404, "Investigation not found")

    # assets — grouped by T-Intel category
    async with db.execute(
        "SELECT * FROM assets WHERE investigation_id = ? AND status = 'active' ORDER BY type, value",
        (inv_id,)
    ) as cur:
        all_assets = [dict(r) for r in await cur.fetchall()]

    grouped_assets = {group: [] for group in TINTEL_GROUPS}
    for asset in all_assets:
        for group, types in TINTEL_GROUPS.items():
            if asset["type"] in types:
                grouped_assets[group].append(asset)

    # scope
    async with db.execute(
        "SELECT * FROM scope WHERE investigation_id = ? ORDER BY type, value", (inv_id,)
    ) as cur:
        scope_rows = [dict(r) for r in await cur.fetchall()]

    scope = {
        "in_scope":     [r for r in scope_rows if r["type"] == "in_scope"],
        "out_of_scope": [r for r in scope_rows if r["type"] == "out_of_scope"],
        "rules":        [r for r in scope_rows if r["type"] == "rule"],
        "rewards":      [r for r in scope_rows if r["type"] == "reward"],
    }

    # findings summary — counts only, not full records
    async with db.execute(
        """SELECT severity, status, COUNT(*) as count
           FROM findings WHERE investigation_id = ?
           GROUP BY severity, status""",
        (inv_id,)
    ) as cur:
        finding_rows = [dict(r) for r in await cur.fetchall()]

    findings_summary = {
        "open":      0, "submitted": 0, "resolved": 0,
        "critical":  0, "high": 0, "medium": 0, "low": 0, "informational": 0,
        "total":     0,
    }
    for row in finding_rows:
        findings_summary[row["status"]] = findings_summary.get(row["status"], 0) + row["count"]
        findings_summary[row["severity"]] = findings_summary.get(row["severity"], 0) + row["count"]
        findings_summary["total"] += row["count"]

    # recent timeline — last 10 events
    async with db.execute(
        "SELECT * FROM timeline WHERE investigation_id = ? ORDER BY created_at DESC LIMIT 10",
        (inv_id,)
    ) as cur:
        recent_activity = [dict(r) for r in await cur.fetchall()]

    return {
        "investigation": dict(inv),
        "assets":        grouped_assets,
        "scope":         scope,
        "findings":      findings_summary,
        "recent_activity": recent_activity,
    }
