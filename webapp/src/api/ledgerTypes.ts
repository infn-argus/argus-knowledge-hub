/** Types of the fact ledger API (`/v1/ledger`, `/v1/installations`, `/v1/access-points`). */

export interface TemporalValue {
  kind: "date" | "before_records" | "unscheduled" | "open" | "unknown_past" | "range";
  nominal?: string;
  precision?: "instant" | "day" | "month" | "year";
  bound?: string;
  /** kind "range": an inferred instant somewhere between these two observations. */
  earliest?: string;
  latest?: string;
}

export interface RecordBrief {
  uid: string;
  key: string;
  name: string;
  type: string;
  record_status: string;
}

export interface InstallationView {
  uid: string;
  key: string;
  status: "Proposed" | "Confirmed" | "Rejected" | "Withdrawn";
  valid_from: TemporalValue | null;
  valid_until: TemporalValue | null;
  removal_reason: string | null;
  temporal_state: "Planned" | "Future" | "Current" | "Ended";
  temporal_certainty: "definite" | "possible";
  position: RecordBrief | null;
  asset: RecordBrief | null;
}

export interface FactContributor {
  status: string;
  rank: string | null;
  effective: boolean;
  kind: "claim" | "decision";
  claim_id?: string;
  value?: unknown;
  polarity?: string;
  method?: string;
  rule_id?: string | null;
  stream?: string;
  source_kind?: string | null;
  revision?: string | null;
  observed_at?: string | null;
  evidence?: Record<string, unknown> | null;
  decision_id?: string;
  decision?: string;
  actor?: string;
  at?: string;
  reason?: string | null;
}

export interface RecordFacts {
  record: RecordBrief;
  source_refs: string[];
  facts: { predicate: string; member: string | null; contributors: FactContributor[] }[];
}

export interface ReviewQueue {
  conflicts: {
    conflict_id: string;
    type: string;
    severity: "blocking" | "non-blocking";
    predicate: string | null;
    member: string | null;
    detail: Record<string, unknown>;
    record: RecordBrief | null;
  }[];
  proposals: {
    claim_id: string;
    predicate: string;
    member: string | null;
    value: unknown;
    method: string;
    rule_id: string | null;
    stream_id: string;
    record: RecordBrief | null;
  }[];
  held_revisions: { revision_id: string; stream_id: string; revision: string; observed_at: string; reasons: string[] }[];
  provisional_records: RecordBrief[];
  installation_proposals: (Omit<InstallationView, "temporal_state" | "temporal_certainty"> & {
    position: RecordBrief | null;
    asset: RecordBrief | null;
  })[];
  counts: {
    conflicts: number;
    blocking: number;
    proposals: number;
    held_revisions: number;
    installation_proposals: number;
  };
}

export interface Decision {
  kind: "accept" | "reject" | "confirm" | "supersede" | "retract" | "revoke" | "resolve_conflict";
  subject_uid?: string;
  predicate?: string;
  member?: string | null;
  value?: unknown;
  supersedes?: string[];
  target?: Record<string, unknown>;
  reason?: string;
}

export interface AccessPointView {
  uid: string;
  key: string;
  address: string | null;
  record_status: string;
  position_uid: string | null;
  position: RecordBrief | null;
  in_service_from: TemporalValue | null;
  in_service_until: TemporalValue | null;
  successor: string | null;
  successor_record: RecordBrief | null;
}

export interface AddressUse {
  access_point_uid: string;
  position: RecordBrief | null;
  asset: RecordBrief | null;
  certainty: "definite" | "possible";
}

export interface PortCandidate {
  port_uid: string;
  label: string;
}

export interface SegmentPort {
  status: "attached" | "unresolved" | "confirmation_required" | "invalid" | "not_applicable";
  position_uid?: string | null;
  installation_uid?: string;
  unit_uid?: string;
  unit?: RecordBrief | null;
  port_uid?: string;
  port?: RecordBrief | null;
  required?: Record<string, unknown>;
  reason?: string;
  failed?: string;
  candidates?: PortCandidate[];
  ports?: (PortCandidate & { failed: string | null })[];
  evidence?: Record<string, unknown>;
}

export interface TicketLinkView {
  asset_uid: string;
  name: string | null;
  key: string | null;
  type: string | null;
  role: "subject" | "related" | "involved_equipment" | "involved_position";
  certainty: "definite" | "possible";
  origin: "ticket" | "derived" | "migration-split";
  detail: { incident?: [string, string]; source?: string } | null;
}

export interface RecordTickets {
  counts: { subject: number; involved: number };
  involved: {
    ticket_uid: string;
    key: string;
    title: string;
    state: string;
    role: string;
    certainty: "definite" | "possible";
    origin: string;
  }[];
}

export interface RuleEntry {
  rule_id: string;
  family: string;
  meaning: string;
  supersedes: string | null;
  carries_rejections: boolean;
  implementations: string[];
  signature: string;
  active: boolean;
  active_impl: string | null;
}

export interface ExitCriterion {
  id: string;
  text: string;
  ok: boolean;
  attested?: boolean;
  detail?: Record<string, unknown>;
}

export interface ReconciliationDifference {
  id: string;
  section: string;
  item: string;
  message: string;
  explained_by: string | null;
  sha256?: string;
  size?: number;
}

export interface ReconciliationBody {
  domain: string;
  manifest_hash: string;
  watermark: Record<string, unknown> | null;
  sections: Record<string, { source: number; argus: number }>;
  differences: ReconciliationDifference[];
  unexplained: number;
  passed: boolean;
  at: string;
}

export interface DomainView {
  id: string;
  workspace_id: string;
  name: string;
  resource: string;
  stage: "T0" | "T1" | "T2" | "T3" | "T4" | "T5";
  stage_name: string;
  stream_ids: string[];
  pilot: boolean;
  archive_url: string | null;
  watermark: Record<string, unknown> | null;
  manifest_hash: string | null;
  frozen_at: string | null;
  exited_at: string | null;
  authoritative: boolean;
  latest_report: { id: string; passed: boolean; created_at: string; unexplained: number; body_hash: string } | null;
  streams: { id: string; kind: string; frozen_at: string | null }[];
}

export interface DomainDetail extends DomainView {
  exit_criteria: ExitCriterion[];
  report: ReconciliationBody | null;
  stages: Record<string, string>;
}

export interface LookupHit {
  status: "migrated";
  kind: "asset" | "ticket";
  uid: string;
  key: string;
  name: string;
  workspace_id: string;
  path: string;
  via: string;
}

export interface ValueHistory {
  current: unknown;
  history: { at: string; until: string | null; value: unknown; by: string | null; via: string; kind: string; reason?: string | null }[];
}

export interface EquipmentState {
  lifecycle: { state: string | null; recorded: string | null; allowed: string[]; installation: Record<string, unknown> | null };
  states: string[];
  custody: ValueHistory;
  location: ValueHistory;
  lifecycle_history: ValueHistory;
  designated_spare: boolean;
}

export interface SpareView {
  uid: string;
  key: string;
  name: string;
  type: string;
  product_model: string | null;
  location: string | null;
  custodian: string | null;
  lifecycle: string | null;
  available: boolean;
  why_not: string | null;
}

export interface AuditEntry {
  at: string;
  type: "record" | "decision" | "fact" | "identity" | "conflict";
  kind: string;
  actor?: string;
  predicate?: string | null;
  value?: unknown;
  before?: unknown;
  after?: unknown;
  cause?: string;
  reason?: string | null;
  decision_id?: string;
  source_ref?: string;
  conflict_type?: string;
}

export interface BulkChangeView {
  id: string;
  actor: string;
  description: string | null;
  spec: Record<string, unknown>;
  count: number;
  state: "previewed" | "awaiting_approval" | "applied" | "undone";
  approved_by: string | null;
  needs_approval: boolean;
  threshold: number;
  batch_id: string | null;
  created_at: string;
  applied_at: string | null;
  preview: { uid: string; key: string; name: string; type: string; changes: { predicate: string; before: unknown; after: unknown }[] }[];
}

export interface AuditDigestView {
  day: string;
  digest: string;
  prev_digest: string | null;
  counts: Record<string, number>;
  sealed_at: string;
}
