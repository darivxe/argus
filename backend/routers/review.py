"""
/review endpoint.
POST /investigations/{inv_id}/findings/{fid}/review

Loads full investigation context, sends to Claude, saves result
as a finding_review record. Full history preserved across runs.
"""
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from aiosqlite import Connection
from ..core.database import get_db
from ..core.ids import generate_id
from ..core.timeline import log_event

router = APIRouter(prefix="/investigations", tags=["review"])

async def _build_review_prompt(inv_id: str, fid: str, db: Connection) -> tuple[str, str]:
    """Build system prompt and user message for the /review call."""

    # investigation
    async with db.execute("SELECT * FROM investigations WHERE id = ?", (inv_id,)) as cur:
        inv = dict(await cur.fetchone())

    # finding
    async with db.execute("SELECT * FROM findings WHERE id = ? AND investigation_id = ?", (fid, inv_id)) as cur:
        finding = await cur.fetchone()
    if not finding:
        raise HTTPException(404, "Finding not found")
    finding = dict(finding)

    # scope
    async with db.execute("SELECT type, value, notes FROM scope WHERE investigation_id = ?", (inv_id,)) as cur:
        scope_rows = [dict(r) for r in await cur.fetchall()]

    in_scope     = [r["value"] for r in scope_rows if r["type"] == "in_scope"]
    out_of_scope = [r["value"] for r in scope_rows if r["type"] == "out_of_scope"]
    rules        = [r["value"] for r in scope_rows if r["type"] == "rule"]

    # assets relevant to this finding
    async with db.execute(
        """SELECT a.type, a.value FROM assets a
           INNER JOIN finding_assets fa ON fa.asset_id = a.id
           WHERE fa.finding_id = ?""", (fid,)
    ) as cur:
        affected_assets = [dict(r) for r in await cur.fetchall()]

    # all active assets for context
    async with db.execute(
        "SELECT type, value FROM assets WHERE investigation_id = ? AND status = 'active'", (inv_id,)
    ) as cur:
        all_assets = [dict(r) for r in await cur.fetchall()]

    # recent notes for context
    async with db.execute(
        "SELECT content FROM notes WHERE investigation_id = ? ORDER BY created_at DESC LIMIT 10", (inv_id,)
    ) as cur:
        notes = [r[0] for r in await cur.fetchall()]

    system_prompt = """You are a security review assistant embedded in Argus, a pentester's workstation.

Your job is to review a bug bounty or pentest finding and evaluate it against the program scope, rules, and available evidence.

You must respond ONLY with a valid JSON object — no markdown, no explanation, no preamble. The JSON must have exactly these fields:

{
  "scope_alignment": "in_scope" | "out_of_scope" | "unclear",
  "suggested_severity": "critical" | "high" | "medium" | "low" | "informational",
  "confidence": <integer 0-100>,
  "evidence_quality": "strong" | "moderate" | "weak" | "insufficient",
  "missing_evidence": "<string or null>",
  "submission_readiness": "ready" | "needs_work" | "not_ready",
  "reasoning": "<detailed markdown reasoning>"
}

Be conservative with confidence. If scope is ambiguous, say so. Never overstate certainty.
Base your evaluation strictly on the evidence provided — do not assume what was not given."""

    user_message = f"""## Investigation
Target: {inv["target"]}
Program: {inv.get("program", "Unknown")}
Platform: {inv.get("platform", "Unknown")}

## Scope
In scope:
{chr(10).join(f"  - {s}" for s in in_scope) if in_scope else "  - Not specified"}

Out of scope:
{chr(10).join(f"  - {s}" for s in out_of_scope) if out_of_scope else "  - Not specified"}

Program rules:
{chr(10).join(f"  - {r}" for r in rules) if rules else "  - Not specified"}

## Finding
Title: {finding["title"]}
Severity (researcher assessment): {finding["severity"]}
Status: {finding["status"]}

Description:
{finding.get("description") or "Not provided"}

Reproduction steps:
{finding.get("reproduction_steps") or "Not provided"}

Remediation notes:
{finding.get("remediation") or "Not provided"}

Affected assets:
{chr(10).join(f"  - [{a['type']}] {a['value']}" for a in affected_assets) if affected_assets else "  - None linked"}

## Known Infrastructure
{chr(10).join(f"  [{a['type']}] {a['value']}" for a in all_assets[:30]) if all_assets else "  None recorded"}

## Researcher Notes (recent)
{chr(10).join(f"  - {n}" for n in notes) if notes else "  None"}

Review this finding and return your JSON evaluation."""

    return system_prompt, user_message


@router.post("/{inv_id}/findings/{fid}/review")
async def review_finding(inv_id: str, fid: str, db: Connection = Depends(get_db)):
    async with db.execute("SELECT id FROM investigations WHERE id = ?", (inv_id,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(404, "Investigation not found")

    # get settings for API key and model
    async with db.execute("SELECT anthropic_api_key, default_model FROM settings WHERE id = 1") as cur:
        settings = dict(await cur.fetchone())

    api_key = settings.get("anthropic_api_key")
    if not api_key:
        raise HTTPException(400, "Anthropic API key not configured. Set it in Settings.")

    model = settings.get("default_model") or "claude-sonnet-4-6"

    system_prompt, user_message = await _build_review_prompt(inv_id, fid, db)

    # call Claude
    import httpx
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 1024,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_message}],
            }
        )

    if response.status_code != 200:
        raise HTTPException(502, f"Claude API error: {response.text}")

    raw = response.json()["content"][0]["text"].strip()

    # parse JSON response
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # strip any accidental markdown fences
        clean = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)

    # validate required fields
    required = {"scope_alignment", "suggested_severity", "confidence",
                "evidence_quality", "submission_readiness", "reasoning"}
    if not required.issubset(result.keys()):
        raise HTTPException(502, "Claude returned incomplete review data")

    # clamp confidence
    confidence = max(0, min(100, int(result["confidence"])))

    # save review record
    rid = generate_id()
    await db.execute(
        """INSERT INTO finding_reviews
           (id, finding_id, scope_alignment, suggested_severity, confidence,
            evidence_quality, missing_evidence, submission_readiness, reasoning)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (rid, fid,
         result["scope_alignment"],
         result["suggested_severity"],
         confidence,
         result["evidence_quality"],
         result.get("missing_evidence"),
         result["submission_readiness"],
         result["reasoning"])
    )
    await log_event(db, inv_id, 'finding_reviewed',
                    f"Finding reviewed — {result['suggested_severity']} ({confidence}% confidence) — {result['submission_readiness']}",
                    {"finding_id": fid, "review_id": rid,
                     "scope": result["scope_alignment"],
                     "severity": result["suggested_severity"],
                     "confidence": confidence,
                     "readiness": result["submission_readiness"]})
    await db.commit()

    # return full review
    async with db.execute("SELECT * FROM finding_reviews WHERE id = ?", (rid,)) as cur:
        return dict(await cur.fetchone())
