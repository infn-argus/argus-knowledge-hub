/** Portable exports and imports (docs/export-import-design.md). */

export interface PortabilityConfig {
  repositories: string[];
  artifact_stores: string[];
  signing: { configured: boolean; key_id: string | null; principal: string | null };
  trusted_keys: boolean;
  restricted_classes: string[];
  export_modes: string[];
  import_modes: string[];
  outcomes: string[];
  is_admin: boolean;
}

export interface ArchiveLabels {
  complete: boolean;
  selective: boolean;
  full: boolean;
  incremental: boolean;
  signed: boolean;
  encrypted: boolean;
  artifact_complete: boolean;
  evidence_only: boolean;
  git_published: boolean;
  verified: boolean;
  restorable: boolean;
}

export interface Dependency {
  id: string;
  rule: string;
  workspace: string | null;
  count?: number;
  examples?: { from: string; to: string }[];
  options: string[];
  outcome: string | null;
  problem?: string;
}

export interface ExportAnalysis {
  closure?: {
    dependencies: Dependency[];
    automatic: { rule: string; outcome: string; detail: string }[];
    unresolved: string[];
    blocked: string[];
    workspaces?: string[];
  };
  restriction?: { included: string[]; excluded_classes: string[]; fields_hidden: boolean };
  estimate?: { records: number; tickets: number; claim_events: number; attachments: number; attachment_bytes: number };
  ready?: boolean;
  warnings?: string[];
}

export interface Watermark {
  label: number;
  tables: Record<string, number>;
  snapshot_at: string;
}

export interface PortabilityError {
  error: string;
  code: string;
  [k: string]: unknown;
}

export interface ExportView {
  id: string;
  mode: string;
  state: string;
  risk: "normal" | "high";
  workspaces: string[];
  classifications: string[];
  base_export_id: string | null;
  destination: { repository?: string | null; artifact_store?: string | null };
  decisions: Record<string, string>;
  requested_by: string;
  approved_by: string | null;
  analysis: ExportAnalysis;
  watermark: Watermark | null;
  manifest_sha256: string | null;
  git: { repository?: string; repository_id?: string; commit?: string; tag?: string; parent?: string | null;
         previous_tag?: string | null; root_commit?: string };
  error: PortabilityError | null;
  labels: ArchiveLabels;
  created_at: string | null;
}

export interface FamilyManifest {
  group: string;
  authoritative: boolean;
  rows: number;
  sha256: string;
  chunks: { file: string; rows: number; first: string | null; last: string | null; bytes: number }[];
}

export interface ArchiveManifest {
  format: string;
  export_id: string;
  mode: string;
  labels: Record<string, boolean>;
  argus: { application_version: string; database_schema: string | null; instance_id: string; instance_name?: string };
  workspaces: string[];
  watermark: Watermark;
  base: { export_id: string; watermark: Watermark } | null;
  versions: Record<string, string | null>;
  families: Record<string, FamilyManifest>;
  blobs: { count: number; bytes: number; manifest: string; stores: string[] };
  classifications: { included: string[]; excluded_classes: string[]; fields_hidden: boolean };
  closure: { dependencies: Dependency[]; automatic: { rule: string; outcome: string; detail: string }[];
             decisions: Record<string, string> };
  invariants?: { ok: boolean | null; codes?: string[] };
  signature?: { algorithm: string; key_id: string; principal: string };
  created_at: string;
  requested_by: string;
  approved_by: string | null;
}

export interface DryRunReport {
  mode: string;
  export_id: string;
  ready: boolean;
  note?: string;
  workspaces?: { archive: string; local: string; exists: boolean }[];
  families?: Record<string, Record<string, number>>;
  blocking?: { family: string; key: string; reason: string }[];
  blocking_count?: number;
  catalogue_conflicts?: { family: string; key: string; reason: string }[];
  identity_candidates?: { archive: string; here: string; identifier: string; value: string }[];
  unresolved_references?: { family: string; key: string; missing: [string, string][] }[];
  unresolved_reference_count?: number;
  unresolved_references_outcome?: string;
  identities?: { user: string; note: string }[];
  governance_not_loaded?: string[];
  chain?: { status: string; problem?: string; applied?: number };
}

export interface ImportView {
  id: string;
  mode: string;
  state: string;
  source: { repository?: string; ref?: string; expected_commit?: string };
  commit: string | null;
  requested_by: string;
  approved_by: string | null;
  decisions: Record<string, unknown>;
  manifest: Pick<ArchiveManifest, "export_id" | "mode" | "workspaces" | "watermark" | "argus" | "labels" |
    "classifications" | "base" | "blobs"> | null;
  verification: {
    git?: { repository_id: string; root_commit: string; commit: string; tag: string | null; tag_object: string | null;
            signed_by: string; export_id: string; previous_tag: string | null; lfs_pointers: unknown[] };
    upload?: { bytes: number; sha256: string };
    checkpoint?: { files: number; chunks: number; rows: number; blobs: number; blob_bytes: number;
                   signed_by: string | null; artifact_complete: boolean; manifest_sha256: string };
  };
  dry_run: DryRunReport | Record<string, never>;
  checkpoints: { done: number };
  reconciliation_passed: boolean | null;
  reconciliation_sha256: string | null;
  error: PortabilityError | null;
  labels: ArchiveLabels;
  created_at: string | null;
}

export interface FamilyReconciliation {
  rows: number;
  expected_rows: number;
  sha256: string;
  expected_sha256: string;
  ok: boolean;
  mismatch_count: number;
  mismatches: { key: string; missing: boolean; fields: string[] }[];
}

export interface ReconciliationReport {
  passed: boolean;
  evidence_only?: boolean;
  already_applied?: boolean;
  export_id: string;
  families?: Record<string, FamilyReconciliation>;
  projections?: Record<string, { exported: number; rebuilt: number; ok: boolean }>;
  invariants?: { ok: boolean | null; exported_ok: boolean | null; acceptable: boolean };
  deferred_references?: { family: string; key: string; missing: [string, string][]; row: string }[];
  rebuild?: { events_written_by_rebuild: Record<string, number> };
  signature?: { algorithm: string; key_id: string; principal: string };
}

export interface ProvenanceView {
  git: ImportView["verification"]["git"] | null;
  origin: ArchiveManifest["argus"] | null;
  watermark: Watermark | null;
  reconciliation_sha256: string | null;
  events: { seq: number; kind: string; from: string | null; to: string | null; actor: string; at: string;
            detail: Record<string, unknown> | null }[];
}
