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
