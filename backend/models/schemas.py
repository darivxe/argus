from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

# ── Investigations ────────────────────────────────────────────

class InvestigationCreate(BaseModel):
    target: str
    program: Optional[str] = None
    platform: Optional[str] = None
    description: Optional[str] = None

class InvestigationUpdate(BaseModel):
    status: Optional[Literal['active', 'paused', 'completed']] = None
    description: Optional[str] = None
    program: Optional[str] = None
    platform: Optional[str] = None

class Investigation(BaseModel):
    id: str
    target: str
    program: Optional[str]
    platform: Optional[str]
    description: Optional[str]
    status: str
    created_at: str
    updated_at: str
    last_activity: str

# ── Assets ───────────────────────────────────────────────────

AssetType = Literal[
    'domain', 'subdomain', 'ip', 'url', 'port', 'service',
    'framework', 'cdn', 'waf', 'cms', 'cloud_provider', 'language',
    'endpoint', 'parameter', 'header'
]

class AssetCreate(BaseModel):
    type: AssetType
    value: str
    parent_id: Optional[str] = None
    notes: Optional[str] = None
    source: Literal['manual', 'imported', 'committed', 'discovered'] = 'manual'

class AssetStatusUpdate(BaseModel):
    status: Literal['active', 'ignored', 'out_of_scope', 'archived']

# ── Scope ────────────────────────────────────────────────────

class ScopeCreate(BaseModel):
    type: Literal['in_scope', 'out_of_scope', 'rule', 'reward']
    value: str
    notes: Optional[str] = None

# ── Findings ─────────────────────────────────────────────────

class FindingCreate(BaseModel):
    title: str
    description: Optional[str] = None
    severity: Literal['critical', 'high', 'medium', 'low', 'informational'] = 'medium'
    reproduction_steps: Optional[str] = None
    remediation: Optional[str] = None

class FindingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[Literal['critical', 'high', 'medium', 'low', 'informational']] = None
    status: Optional[Literal['open', 'submitted', 'resolved', 'duplicate', 'na']] = None
    reproduction_steps: Optional[str] = None
    remediation: Optional[str] = None

# ── Notes ────────────────────────────────────────────────────

class NoteCreate(BaseModel):
    content: str
    source: Literal['manual', 'ai', 'committed'] = 'manual'

# ── Reports ──────────────────────────────────────────────────

class ReportCreate(BaseModel):
    title: str
    author: Literal['ai', 'researcher'] = 'researcher'
    content: str = ''

class ReportUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None

# ── Commit command (from terminal) ───────────────────────────

class CommitPayload(BaseModel):
    investigation_id: str
    command: Literal['finding', 'note', 'asset', 'endpoint', 'technology']
    value: str
    severity: Optional[Literal['critical', 'high', 'medium', 'low', 'informational']] = None
    asset_type: Optional[AssetType] = None

# ── Review ───────────────────────────────────────────────────

class ReviewResult(BaseModel):
    id: str
    finding_id: str
    scope_alignment: Literal['in_scope', 'out_of_scope', 'unclear']
    suggested_severity: Literal['critical', 'high', 'medium', 'low', 'informational']
    confidence: int
    evidence_quality: Literal['strong', 'moderate', 'weak', 'insufficient']
    missing_evidence: Optional[str]
    submission_readiness: Literal['ready', 'needs_work', 'not_ready']
    reasoning: str
    created_at: str

# ── Settings ─────────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    anthropic_api_key: Optional[str] = None
    default_model: Optional[str] = None
    theme: Optional[str] = None
    workspace_path: Optional[str] = None
    provider: Optional[str] = None
