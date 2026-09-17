export interface SchemaAttribute {
  id?: string;
  name: string;
  key?: string;
  type: string;
  required?: boolean;
  unique?: boolean;
  indexed?: boolean;
  default?: unknown;
  description?: string;
  options?: { id: string; value: string }[];
  referenceType?: string;
  referenceSchemaUid?: string;
  includeChildren?: boolean;
  multiValue?: boolean;
  minCardinality?: number;
  maxCardinality?: number;
  regex?: string;
  readOnly?: boolean;
  visible?: boolean;
  order?: number;
  global?: boolean;
}

export const ATTRIBUTE_TYPES = [
  "string",
  "text",
  "integer",
  "float",
  "boolean",
  "date",
  "datetime",
  "enumeration",
  "reference",
  "attachment",
  "user",
  "current_user",
] as const;

export interface AppSchema {
  uid: string;
  workspace_id: string;
  name: string;
  description: string | null;
  is_concrete: boolean;
  parent_schema_uid: string | null;
  attributes: SchemaAttribute[];
  metadata: Record<string, unknown>;
  version: number;
  icon_uid: string | null;
  is_global: boolean;
  applies_to: "objects" | "tickets" | "documents";
  created_at: string;
  updated_at: string;
}

export interface SchemaInput {
  uid?: string;
  name: string;
  description?: string | null;
  is_concrete: boolean;
  parent_schema_uid?: string | null;
  attributes: SchemaAttribute[];
  metadata?: Record<string, unknown>;
  is_global?: boolean;
  applies_to?: "objects" | "tickets" | "documents";
}

export interface Asset {
  uid: string;
  workspace_id: string;
  schema_uid: string;
  key: string;
  name: string;
  type: string;
  avatar_icon_uid: string | null;
  attributes: Record<string, unknown>;
  inbound_relations: string[];
  outbound_relations: string[];
  is_global: boolean;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface AssetInput {
  uid?: string;
  schema_uid: string;
  key: string;
  name: string;
  type: string;
  avatar_icon_uid?: string | null;
  attributes: Record<string, unknown>;
  inbound_relations?: string[];
  outbound_relations?: string[];
  is_global?: boolean;
}

export interface Relation {
  id: number;
  workspace_id: string;
  from_asset_uid: string;
  to_asset_uid: string;
  relation_type: string;
  created_at: string;
}

export interface Issue {
  uid: string;
  workspace_id: string;
  asset_uid: string | null;
  schema_uid: string | null;
  attributes: Record<string, unknown>;
  title: string;
  description: string | null;
  state: string;
  priority: string | null;
  assignee: string | null;
  labels: string[];
  due_date: string | null;
  closed_at: string | null;
  created_by: string | null;
  version: number;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface IssueInput {
  uid?: string;
  asset_uid?: string | null;
  schema_uid?: string | null;
  attributes?: Record<string, unknown>;
  title: string;
  description?: string | null;
  state?: string;
  priority?: string | null;
  assignee?: string | null;
  labels?: string[];
  due_date?: string | null;
  created_by?: string | null;
}

export interface IssueComment {
  uid: string;
  issue_uid: string;
  author: string;
  body: string;
  created_at: string;
  updated_at: string;
}

export interface AssetComment {
  uid: string;
  asset_uid: string;
  author: string;
  text: string;
  created: string;
  updated: string;
  backend_id: string | null;
  backend_url: string | null;
}

export interface AssetHistory {
  uid: string;
  asset_uid: string;
  type: string;
  author: string;
  details: string;
  timestamp: string;
  backend_id: string | null;
}

export interface AssetTicket {
  /** The ticket in this application, when this row corresponds to one. */
  issue_uid?: string | null;
  uid: string;
  asset_uid: string;
  ticket_key: string;
  summary: string;
  type: string;
  status: string;
  created: string;
  updated: string;
  backend_id: string | null;
  backend_url: string | null;
}

export const LABEL_TYPES = ["qrcode", "barcode", "serial", "rfid"] as const;
export const LABEL_ISSUERS = ["user", "vendor", "system"] as const;

export interface AssetLabel {
  uid: string;
  asset_uid: string;
  type: string;
  value: string;
  namespace: string | null;
  issuer: string;
  verified: boolean;
  confidence: number | null;
  created_at: string;
  updated_at: string;
}

export interface AssetLabelInput {
  uid?: string;
  type: string;
  value: string;
  namespace?: string | null;
  issuer: string;
  verified?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface AssetLabelSearchResult {
  uid: string;
  type: string;
  value: string;
  namespace: string | null;
  issuer: string;
  verified: boolean;
  asset_uid: string;
  asset_name: string;
  asset_key: string;
}

export interface Attachment {
  uid: string;
  workspace_id: string;
  asset_uid: string | null;
  document_revision_uid?: string | null;
  /** "dxf-of:<uid>" on a converted drawing; identifies what it came from. */
  backend_id?: string | null;
  /** Carries "preview-failed: …" when a drawing could not be converted. */
  backend_url?: string | null;
  filename: string;
  mime_type: string | null;
  file_size: number | null;
  author: string | null;
  created_at: string;
}

export interface GlobalValueOption {
  id: string;
  value: string;
  responsible?: string;
  meaning?: string;
}

export interface GlobalValue {
  uid: string;
  workspace_id: string;
  name: string;
  key: string;
  type: string;
  applies_to: "objects" | "tickets" | "documents";
  options: GlobalValueOption[] | null;
  default_value: string | null;
  constraints: Record<string, unknown> | null;
  required: boolean;
  unique: boolean;
  indexed: boolean;
  multi_value: boolean;
  min_cardinality: number | null;
  max_cardinality: number | null;
  reference_type: string | null;
  egu: string | null;
  allowed_egu_list: string[] | null;
  read_only: boolean;
  visible: boolean;
  enabled: boolean;
  is_system_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface GlobalValueInput {
  uid?: string;
  name: string;
  key: string;
  type: string;
  applies_to?: "objects" | "tickets" | "documents";
  options?: GlobalValueOption[] | null;
  default_value?: string | null;
  required?: boolean;
  unique?: boolean;
  indexed?: boolean;
  multi_value?: boolean;
  read_only?: boolean;
  visible?: boolean;
  enabled?: boolean;
}

/** The sources an import can run against. Kept in one place: the job type
 * used to list only two of them, so any code branching on a Confluence or
 * ticket job read as unreachable. */
export type ImportSource = "jira" | "jira-issues" | "confluence" | "git";

export interface ImportJob {
  uid: string;
  workspace_id: string;
  source: ImportSource;
  status: "pending" | "running" | "succeeded" | "failed";
  progress: string | null;
  counts: Record<string, number>;
  warnings: string[];
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export type MergeStrategy = "override" | "no_override" | "update_if_newer" | "remove_all_before";

export type TransferMode = "copy" | "move";

export interface TransferRequest {
  target_workspace_id: string;
  mode: TransferMode;
  type_uids?: string[];
  include_instances?: boolean;
  include_descendant_types?: boolean;
  asset_uids?: string[];
  document_uids?: string[];
  issue_uids?: string[];
  /** Copy only: merge into a same-named type/object at the target instead
   * of refusing. Move never merges, regardless of this flag. */
  force?: boolean;
}

export interface TransferJob {
  uid: string;
  workspace_id: string;
  target_workspace_id: string;
  mode: TransferMode;
  status: "pending" | "running" | "succeeded" | "failed";
  progress: string | null;
  counts: Record<string, number>;
  warnings: string[];
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export const MERGE_STRATEGIES: { value: MergeStrategy; label: string; description: string }[] = [
  {
    value: "override",
    label: "Override",
    description: "Always overwrite matched objects with the source's current values.",
  },
  {
    value: "no_override",
    label: "Don't override",
    description: "Only create new objects; leave already-imported ones untouched.",
  },
  {
    value: "update_if_newer",
    label: "Update if source is more recent",
    description: "Overwrite a matched object only if the source's version is newer.",
  },
  {
    value: "remove_all_before",
    label: "Remove all before importing",
    description: "Delete everything previously imported from this source first, then import fresh.",
  },
];

export interface JiraImportInput {
  source: "jira";
  base_url: string;
  pat: string;
  jira_schema_id: string;
  merge_strategy?: MergeStrategy;
}

export interface GitImportInput {
  source: "git";
  provider: "github" | "gitlab";
  repo_url: string;
  pat: string;
  branch: string;
  merge_strategy?: MergeStrategy;
}

export interface JiraIssueImportInput {
  source: "jira-issues";
  base_url: string;
  pat: string;
  jql: string;
  schema_uid?: string | null;
  link_assets?: boolean;
  merge_strategy?: MergeStrategy;
}

export type ImportInput = JiraImportInput | JiraIssueImportInput | GitImportInput;

export interface ImportConfig {
  uid: string;
  workspace_id: string;
  name: string;
  source: ImportSource;
  merge_strategy: MergeStrategy;
  params: Record<string, string | boolean | null>;
  last_run_at: string | null;
  last_import_job_uid: string | null;
  created_at: string;
  updated_at: string;
}

export interface JiraIssueImportConfigParams {
  source: "jira-issues";
  base_url: string;
  jql: string;
  schema_uid?: string | null;
  link_assets?: boolean;
  pat?: string;
}

export interface JiraImportConfigParams {
  source: "jira";
  base_url: string;
  jira_schema_id: string;
  pat?: string;
}

export interface GitImportConfigParams {
  source: "git";
  provider: "github" | "gitlab";
  repo_url: string;
  branch: string;
  /** Omitted for a public repository: no token is sent at all, rather than
   * an empty one, which these APIs reject. */
  pat?: string;
}

export interface ConfluenceImportConfigParams {
  source: "confluence";
  base_url: string;
  space_key?: string | null;
  cql?: string | null;
  link_assets?: boolean;
  pat?: string;
}

/** EPIK8s control configuration: one beamline's values.yaml. Read only —
 * the file in git deploys the accelerator. */
export interface Epik8sImportConfigParams {
  source: "epik8s";
  provider: "github" | "gitlab";
  repo_url: string;
  branch: string;
  path: string;
  /** Make an Access Point for an address no object in the inventory carries,
   * marked as needing confirmation; otherwise only report it. */
  create_missing_nodes?: boolean;
  pat?: string;
}

export type ImportConfigParams =
  | JiraImportConfigParams
  | ConfluenceImportConfigParams
  | JiraIssueImportConfigParams
  | GitImportConfigParams
  | Epik8sImportConfigParams;

export interface ImportConfigInput {
  name: string;
  merge_strategy: MergeStrategy;
  config: ImportConfigParams;
}

export interface ImportConfigUpdateInput {
  name?: string;
  merge_strategy?: MergeStrategy;
  config?: ImportConfigParams;
}

export interface Me {
  auth_type: "pat" | "oidc";
  workspace_id: string | null;
  user_id: string | null;
  email: string | null;
  name: string | null;
  is_admin: boolean;
}

export interface Workspace {
  id: string;
  name: string;
  is_global: boolean;
  created_at: string;
}

export interface WorkspaceUpdateInput {
  name?: string;
  is_global?: boolean;
}

export interface MyWorkspace {
  id: string;
  name: string;
  is_global: boolean;
  created_at: string;
  can_read: boolean;
  can_create: boolean;
  can_modify: boolean;
  can_delete: boolean;
  can_read_tickets: boolean;
  can_create_tickets: boolean;
  can_modify_tickets: boolean;
  can_delete_tickets: boolean;
  can_read_documents: boolean;
  can_create_documents: boolean;
  can_modify_documents: boolean;
  can_delete_documents: boolean;
  can_approve_documents: boolean;
}

export interface MissingReferenceIssue {
  asset_uid: string;
  asset_name: string;
  asset_key: string;
  attribute_key: string;
  attribute_name: string;
  attribute_type: string;
  value: string;
}

export interface DanglingObjectIssue {
  relation_id: number;
  from_asset_uid: string;
  to_asset_uid: string;
  relation_type: string;
  reason: string;
}

export interface OrphanedObjectIssue {
  asset_uid: string;
  name: string;
  key: string;
}

export interface IntegrityReport {
  missing_references: MissingReferenceIssue[];
  dangling_objects: DanglingObjectIssue[];
  orphaned_objects: OrphanedObjectIssue[];
  counts: {
    assets_scanned: number;
    missing_references: number;
    dangling_objects: number;
    orphaned_objects: number;
  };
}

export interface RelinkResult {
  assets_scanned: number;
  assets_updated: number;
  values_relinked: number;
}

export interface CleanupOptions {
  clear_missing_references?: boolean;
  delete_orphaned_objects?: boolean;
  remove_dangling_relations?: boolean;
}

export interface CleanupResult {
  cleared_references: number;
  deleted_orphaned_objects: number;
  removed_dangling_relations: number;
}

export interface MemberDirectoryEntry {
  user_id: string;
  email: string;
  name: string | null;
}

export interface Member {
  user_id: string;
  email: string;
  name: string | null;
  can_read: boolean;
  can_create: boolean;
  can_modify: boolean;
  can_delete: boolean;
  can_read_tickets: boolean;
  can_create_tickets: boolean;
  can_modify_tickets: boolean;
  can_delete_tickets: boolean;
  can_read_documents: boolean;
  can_create_documents: boolean;
  can_modify_documents: boolean;
  can_delete_documents: boolean;
  can_approve_documents: boolean;
}

export interface MemberInput {
  email: string;
  can_read: boolean;
  can_create: boolean;
  can_modify: boolean;
  can_delete: boolean;
  can_read_tickets: boolean;
  can_create_tickets: boolean;
  can_modify_tickets: boolean;
  can_delete_tickets: boolean;
  can_read_documents: boolean;
  can_create_documents: boolean;
  can_modify_documents: boolean;
  can_delete_documents: boolean;
  can_approve_documents: boolean;
}

export interface AdminUser {
  id: string;
  email: string;
  name: string | null;
  is_admin: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface DefaultAccess {
  default_can_read: boolean;
  default_can_create: boolean;
  default_can_modify: boolean;
  default_can_delete: boolean;
  default_can_read_tickets: boolean;
  default_can_create_tickets: boolean;
  default_can_modify_tickets: boolean;
  default_can_delete_tickets: boolean;
  default_can_read_documents: boolean;
  default_can_create_documents: boolean;
  default_can_modify_documents: boolean;
  default_can_delete_documents: boolean;
  default_can_approve_documents: boolean;
}

export interface WorkspaceDetail extends DefaultAccess {
  id: string;
  name: string;
  created_at: string;
}

export type DocumentState = "draft" | "in_review" | "approved" | "published" | "superseded" | "retired";
export type AuthorityLevel = "ufficiale" | "informativo" | "bozza_interna";
export type Confidentiality = "pubblico" | "interno" | "riservato";

export interface DocumentStep {
  ordine?: number;
  testo: string;
  checklist?: boolean;
  voce_critica?: boolean;
}

export interface AppDocument {
  uid: string;
  workspace_id: string;
  code: string;
  title: string;
  document_type_uid: string | null;
  owner_user_id: string | null;
  responsible_service_asset_uid: string | null;
  authority_level: AuthorityLevel;
  confidentiality: Confidentiality;
  source: string;
  /** Readable from every workspace. Never true for a riservato document. */
  is_global: boolean;
  current_revision_uid: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentInput {
  uid?: string;
  /** Null lets the system assign one from the document's type. */
  code: string | null;
  title: string;
  document_type_uid?: string | null;
  owner_user_id?: string | null;
  responsible_service_asset_uid?: string | null;
  authority_level?: AuthorityLevel;
  confidentiality?: Confidentiality;
  source?: string;
  body_markdown?: string | null;
  steps?: DocumentStep[];
  attributes?: Record<string, unknown>;
  valid_from?: string | null;
  valid_until?: string | null;
  next_review_due?: string | null;
}

export interface DocumentUpdateInput {
  title?: string;
  document_type_uid?: string | null;
  owner_user_id?: string | null;
  responsible_service_asset_uid?: string | null;
  authority_level?: AuthorityLevel;
  confidentiality?: Confidentiality;
  is_global?: boolean;
}

export interface DocumentRevision {
  uid: string;
  document_uid: string;
  revision_number: number;
  state: DocumentState;
  body_markdown: string | null;
  steps: DocumentStep[];
  attributes: Record<string, unknown>;
  valid_from: string | null;
  valid_until: string | null;
  next_review_due: string | null;
  authored_by: string | null;
  approved_by: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  published_at: string | null;
  review_comment: string | null;
  superseded_by_uid: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentRevisionInput {
  body_markdown?: string | null;
  steps?: DocumentStep[];
  attributes?: Record<string, unknown>;
  valid_from?: string | null;
  valid_until?: string | null;
  next_review_due?: string | null;
}

export interface DocumentRelation {
  id: number;
  from_document_uid: string;
  to_type: "asset" | "schema" | "document" | "issue";
  to_uid: string;
  relation_type: string;
  created_at: string;
}

export interface IssueHistoryEntry {
  uid: string;
  issue_uid: string;
  type: string;
  author: string;
  field: string | null;
  from_value: string | null;
  to_value: string | null;
  details: string | null;
  timestamp: string;
}

export interface IssueAssetLink {
  asset_uid: string;
  name: string;
  key: string;
  type: string | null;
  relation: string;
}

export interface IssueDocumentLink {
  document_uid: string;
  code: string;
  title: string;
  relation: string;
  relation_id: number;
}

export interface IssueTicketLink {
  link_id: number;
  issue_uid: string;
  title: string;
  state: string;
  source_key: string | null;
  relation: string;
  outgoing: boolean;
}

export interface IssueLinks {
  assets: IssueAssetLink[];
  documents: IssueDocumentLink[];
  tickets: IssueTicketLink[];
}

export interface Role {
  id: string;
  name: string;
  description: string | null;
  permissions: Record<string, string[]>;
  is_system: boolean;
  rank: number;
}

export interface RoleBinding {
  id: number;
  workspace_id: string;
  subject_type: "user" | "group";
  subject_id: string;
  subject_label: string;
  subject_active: boolean;
  role_id: string;
  role_name: string;
  created_at: string | null;
}

export interface RoleBindingInput {
  subject_type: "user" | "group";
  subject_id: string;
  role_id: string;
}

export interface DirectoryGroup {
  uid: string;
  dn: string | null;
  name: string;
  description: string | null;
  email: string | null;
  source: string;
  active: boolean;
  member_count: number;
}

export interface DirectoryGroupMember {
  user_id: string;
  email: string;
  name: string | null;
  username: string | null;
  active: boolean;
  source: string;
}

export interface DirectoryStatus {
  provider: string;
  is_test_data: boolean;
  groups: number;
  active_groups: number;
  users: number;
  last_synced_at: string | null;
}

export interface EffectivePermissions {
  workspace_id: string;
  is_admin: boolean;
  objects: string[];
  tickets: string[];
  documents: string[];
  workspace: string[];
}

export interface LLMConfig {
  workspace_id: string;
  base_url: string;
  model: string;
  embedding_model: string | null;
  vision_model: string | null;
  asr_model: string | null;
  tts_model: string | null;
  /** The key itself is never sent back — only whether one is stored. */
  has_api_key: boolean;
  enabled: boolean;
  allow_confidential: boolean;
  last_checked_at: string | null;
  last_check_ok: boolean | null;
  last_check_error: string | null;
}

export interface LLMConfigInput {
  base_url: string;
  model: string;
  embedding_model?: string | null;
  vision_model?: string | null;
  asr_model?: string | null;
  tts_model?: string | null;
  /** Omitted keeps the stored key; "" clears it. */
  api_key?: string;
  enabled: boolean;
  allow_confidential: boolean;
}

export interface LLMCheckResult {
  ok: boolean;
  error: string | null;
  models: string[];
}

export interface AIStatus {
  configured: boolean;
  enabled: boolean;
  validated: boolean;
  model: string | null;
  has_embeddings: boolean;
  has_vision: boolean;
  has_asr: boolean;
  has_tts: boolean;
  /** Set when these settings belong to another workspace — the shared
   * default — rather than to this one. */
  inherited_from: string | null;
  reason: string | null;
}

export interface MentionedObject {
  uid: string;
  key: string | null;
  name: string | null;
  /** "key" is something somebody wrote down; "name" could be a coincidence. */
  matched_on: string;
}

export interface DraftDocumentResult {
  body_markdown: string;
  mentioned_objects: MentionedObject[];
}

export interface ReviewFinding {
  severity: "high" | "medium" | "low";
  message: string;
}

export interface ReviewDocumentResult {
  findings: ReviewFinding[];
  mentioned_objects: MentionedObject[];
}

export interface DraftTicketResult {
  category: string | null;
  impact: string | null;
  detected_by: string | null;
  system: string | null;
  subsystem: string | null;
  root_cause: string | null;
  corrective_action: string | null;
  mentioned_objects: MentionedObject[];
}

export interface PhotoIdentification {
  type_uid: string | null;
  type_name: string | null;
  name: string | null;
  manufacturer: string | null;
  model: string | null;
  serial: string | null;
  description: string | null;
  visible_text: string[];
  confidence: "high" | "medium" | "low";
  matches: { uid: string; key: string; name: string }[];
  unmatched_keys: string[];
  error: string | null;
}

export interface AISuggestion {
  id: number;
  target_type: string;
  target_uid: string;
  field: string;
  suggested_value: string;
  suggested_label: string | null;
  previous_value: string | null;
  previous_label: string | null;
  target_label: string | null;
  model: string;
  status: string;
  created_at: string;
}

export interface SuggestRunResult {
  considered: number;
  proposed: number;
  unchanged: number;
  failed_batches: number;
}

export interface MarkdownImportResult {
  documents: number;
  attachments: number;
  relations: number;
  skipped: string[];
}

export interface RetypeResult {
  moved: number;
  not_found: string[];
}

export interface BulkDeleteResult {
  deleted: number;
  not_found: string[];
}

export interface Icon {
  uid: string;
  workspace_id: string;
  name: string;
  filename: string;
  mime_type: string | null;
  file_size: number | null;
  is_global: boolean;
  created_at: string;
  updated_at: string;
}

export interface IconUpdate {
  name?: string;
  is_global?: boolean;
}

/** A node in the knowledge graph. `kind` is what the thing *is*, which is
 * also what decides where clicking it goes. */
export interface GraphNode {
  kind: "asset" | "ticket" | "document" | "group" | "person";
  uid: string;
  label: string;
  sublabel: string | null;
  type_name: string | null;
  state: string | null;
  /** Hops from the node the walk started at. */
  depth: number;
}

export interface GraphEdge {
  from_kind: string;
  from_uid: string;
  to_kind: string;
  to_uid: string;
  relation: string;
  /** structure | work | documentation | people */
  via: string;
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** The node cap stopped the walk: what you see is a subset. */
  truncated: boolean;
}

export interface GraphSummary {
  nodes: Record<string, number>;
  edges: Record<string, number>;
}

/** Import sources read almost alike; spell them out so a ticket import
 * isn't mistaken for an object import when reading a list of runs. */
export function importSourceLabel(source: string): string {
  if (source === "jira") return "Jira objects";
  if (source === "jira-issues") return "Jira tickets";
  if (source === "confluence") return "Confluence";
  if (source === "git") return "Git";
  return source;
}

export interface AskStep {
  tool: string;
  arguments: Record<string, unknown>;
  /** The tool's raw JSON result. Shown, not summarised: the point of the
   * Ask page is seeing which records an answer came from. */
  result: string;
  error: string | null;
  seconds: number;
}

export interface AskResult {
  answer: string;
  steps: AskStep[];
  /** "answered" or "exhausted" — an answer given after the lookup limit
   * was cut short and should be read as such. */
  stopped: string;
  error: string | null;
  seconds: number;
}

/** How a workspace's identifier is derived from its name, installation-wide. */
export interface WorkspaceIdRule {
  prefix: string;
  separator: string;
  case: "lower" | "upper" | "keep";
  max_length: number;
}

export interface WorkspaceIdSuggestion {
  id: string;
  /** What the rule produced before a number was added to make it free. */
  base: string;
  taken: boolean;
}
