/** Types of the fact ledger API (`/v1/ledger`, `/v1/installations`). */

export interface TemporalValue {
  kind: "date" | "before_records" | "unscheduled" | "open" | "unknown_past";
  nominal?: string;
  precision?: "instant" | "day" | "month" | "year";
  bound?: string;
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
