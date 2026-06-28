import json
from typing import Any

async def log_event(db, investigation_id: str, event_type: str, description: str, meta: dict[str, Any] | None = None):
    """Append an event to the investigation timeline."""
    from .ids import generate_id
    await db.execute(
        """INSERT INTO timeline (id, investigation_id, event_type, description, meta)
           VALUES (?, ?, ?, ?, ?)""",
        (generate_id(), investigation_id, event_type, description,
         json.dumps(meta) if meta else None)
    )
