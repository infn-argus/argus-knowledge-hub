import { loadSession } from "./session";
import type {
  AppSchema,
  Asset,
  AssetComment,
  AssetHistory,
  AssetInput,
  AssetLabel,
  AssetLabelInput,
  AssetLabelSearchResult,
  AssetTicket,
  Attachment,
  AppDocument,
  BulkDeleteResult,
  DocumentInput,
  DocumentUpdateInput,
  DocumentRevision,
  DocumentRevisionInput,
  DocumentRelation,
  GlobalValue,
  GlobalValueInput,
  Icon,
  IconUpdate,
  ImportConfig,
  ImportConfigInput,
  ImportConfigUpdateInput,
  ImportInput,
  ImportJob,
  Issue,
  IssueComment,
  IssueInput,
  AdminUser,
  CleanupOptions,
  CleanupResult,
  DefaultAccess,
  IntegrityReport,
  Me,
  Member,
  MemberDirectoryEntry,
  MemberInput,
  MyWorkspace,
  RelinkResult,
  AISuggestion,
  AIStatus,
  DraftDocumentResult,
  DraftTicketResult,
  PhotoIdentification,
  ReviewDocumentResult,
  SuggestRunResult,
  LLMCheckResult,
  LLMConfig,
  LLMConfigInput,
  MarkdownImportResult,
  Relation,
  RetypeResult,
  TransferJob,
  TransferRequest,
  Workspace,
  WorkspaceUpdateInput,
  SchemaInput,
  WorkspaceDetail,
  IssueHistoryEntry,
  IssueLinks,
  IssueAssetLink,
  IssueDocumentLink,
  IssueTicketLink,
  Role,
  RoleBinding,
  RoleBindingInput,
  DirectoryGroup,
  DirectoryGroupMember,
  DirectoryStatus,
  EffectivePermissions,
  Graph,
  GraphSummary,
  AskResult,
  WorkspaceIdRule,
  WorkspaceIdSuggestion,
} from "./types";
import type {
  AssetContext,
  DocumentContext,
  HubOverview,
  HubSearchResult,
  TicketContext,
} from "./hubTypes";
import type {
  AccessPointView,
  AddressUse,
  NotificationView,
  AccessReviewView,
  AttachmentCheck,
  RetentionClass,
  RetentionView,
  RetirementStatus,
  MigrationPlanView,
  QueueDashboard,
  GoldenIncident,
  GoldenRun,
  MigrationRow,
  RoleTemplate,
  Rehearsal,
  TicketTransitions,
  WorkflowDef,
  AuditDigestView,
  AuditEntry,
  BulkChangeView,
  EquipmentState,
  SpareView,
  ValueHistory,
  Decision as LedgerDecision,
  DomainDetail,
  DomainView,
  InstallationView,
  LookupHit,
  ReconciliationBody,
  RecordFacts,
  RecordTickets,
  ReviewQueue,
  RuleEntry,
  SegmentPort,
  TemporalValue,
  TicketLinkView,
} from "./ledgerTypes";

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    super(`API error ${status}: ${JSON.stringify(body)}`);
    this.status = status;
    this.body = body;
  }

  /** The message the API meant for a person — FastAPI puts it in `detail`.
   * Null when the body carries no readable message, so callers can fall back
   * to their own wording rather than showing a JSON dump. */
  get detail(): string | null {
    const detail = (this.body as { detail?: unknown } | null)?.detail;
    return typeof detail === "string" ? detail : null;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const session = await loadSession();
  if (!session) throw new Error("Not signed in");

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${session.token}`);
  if (session.workspaceId) headers.set("X-Workspace-Id", session.workspaceId);
  if (!(init.body instanceof FormData) && init.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const resp = await fetch(`${session.baseUrl}${path}`, { ...init, headers });
  if (resp.status === 204) return undefined as T;

  const text = await resp.text();
  const data = text ? JSON.parse(text) : undefined;
  if (!resp.ok) throw new ApiError(resp.status, data);
  return data as T;
}

export async function checkHealth(baseUrl: string): Promise<boolean> {
  try {
    const resp = await fetch(`${baseUrl}/health`);
    return resp.ok;
  } catch {
    return false;
  }
}

export async function checkToken(): Promise<boolean> {
  try {
    await request("/v1/schemas");
    return true;
  } catch {
    return false;
  }
}

const json = (body: unknown) => JSON.stringify(body);

function authHeaders(session: { token: string; workspaceId?: string }): HeadersInit {
  const headers: Record<string, string> = { Authorization: `Bearer ${session.token}` };
  if (session.workspaceId) headers["X-Workspace-Id"] = session.workspaceId;
  return headers;
}

export const schemasApi = {
  list: () => request<AppSchema[]>("/v1/schemas"),
  get: (uid: string) => request<AppSchema>(`/v1/schemas/${uid}`),
  create: (input: SchemaInput) =>
    request<AppSchema>("/v1/schemas", { method: "POST", body: json(input) }),
  update: (uid: string, input: Partial<SchemaInput>) =>
    request<AppSchema>(`/v1/schemas/${uid}`, { method: "PUT", body: json(input) }),
  delete: (uid: string) => request<void>(`/v1/schemas/${uid}`, { method: "DELETE" }),
  uploadIcon: async (uid: string, file: File): Promise<AppSchema> => {
    const session = await loadSession();
    if (!session) throw new Error("Not signed in");
    const form = new FormData();
    form.append("file", file);
    const resp = await fetch(`${session.baseUrl}/v1/schemas/${uid}/icon`, {
      method: "POST",
      headers: authHeaders(session),
      body: form,
    });
    const data = await resp.json();
    if (!resp.ok) throw new ApiError(resp.status, data);
    return data as AppSchema;
  },
  setIconFromLibrary: (uid: string, iconUid: string) =>
    request<AppSchema>(`/v1/schemas/${uid}/icon/${iconUid}`, { method: "PUT" }),
  clearIcon: (uid: string) => request<AppSchema>(`/v1/schemas/${uid}/icon`, { method: "DELETE" }),
};

export const assetsApi = {
  list: (schemaUid?: string) =>
    request<Asset[]>(`/v1/assets${schemaUid ? `?schema_uid=${schemaUid}` : ""}`),
  get: (uid: string) => request<Asset>(`/v1/assets/${uid}`),
  create: (input: AssetInput) =>
    request<Asset>("/v1/assets", { method: "POST", body: json(input) }),
  update: (uid: string, input: Partial<AssetInput>) =>
    request<Asset>(`/v1/assets/${uid}`, { method: "PUT", body: json(input) }),
  delete: (uid: string) => request<void>(`/v1/assets/${uid}`, { method: "DELETE" }),
  bulkDelete: (uids: string[]) =>
    request<BulkDeleteResult>("/v1/assets/bulk-delete", { method: "POST", body: json({ uids }) }),
  uploadAvatar: async (uid: string, file: File): Promise<Asset> => {
    const session = await loadSession();
    if (!session) throw new Error("Not signed in");
    const form = new FormData();
    form.append("file", file);
    const resp = await fetch(`${session.baseUrl}/v1/assets/${uid}/avatar`, {
      method: "POST",
      headers: authHeaders(session),
      body: form,
    });
    const data = await resp.json();
    if (!resp.ok) throw new ApiError(resp.status, data);
    return data as Asset;
  },
  setAvatarFromAttachment: (uid: string, attachmentUid: string) =>
    request<Asset>(`/v1/assets/${uid}/avatar/${attachmentUid}`, { method: "PUT" }),
  clearAvatar: (uid: string) => request<Asset>(`/v1/assets/${uid}/avatar`, { method: "DELETE" }),
};

export const relationsApi = {
  list: () => request<Relation[]>("/v1/relations"),
  create: (fromAssetUid: string, toAssetUid: string, relationType: string) =>
    request<Relation>("/v1/relations", {
      method: "POST",
      body: json({
        from_asset_uid: fromAssetUid,
        to_asset_uid: toAssetUid,
        relation_type: relationType,
      }),
    }),
  delete: (id: number) => request<void>(`/v1/relations/${id}`, { method: "DELETE" }),
};

export const issuesApi = {
  list: (schemaUid?: string) =>
    request<Issue[]>(`/v1/issues${schemaUid ? `?schema_uid=${schemaUid}` : ""}`),
  get: (uid: string) => request<Issue>(`/v1/issues/${uid}`),
  create: (input: IssueInput) =>
    request<Issue>("/v1/issues", { method: "POST", body: json(input) }),
  update: (uid: string, input: Partial<IssueInput>) =>
    request<Issue>(`/v1/issues/${uid}`, { method: "PUT", body: json(input) }),
  delete: (uid: string) => request<void>(`/v1/issues/${uid}`, { method: "DELETE" }),
  bulkDelete: (uids: string[]) =>
    request<BulkDeleteResult>("/v1/issues/bulk-delete", { method: "POST", body: json({ uids }) }),
  labels: () => request<string[]>("/v1/issues/labels"),
  listComments: (uid: string) =>
    request<IssueComment[]>(`/v1/issues/${uid}/comments`),
  addComment: (uid: string, author: string, body: string) =>
    request<IssueComment>(`/v1/issues/${uid}/comments`, {
      method: "POST",
      body: json({ uid: crypto.randomUUID(), author, body }),
    }),
};

export const assetSubresourcesApi = {
  history: (assetUid: string) =>
    request<AssetHistory[]>(`/v1/assets/${assetUid}/history`),
  comments: (assetUid: string) =>
    request<AssetComment[]>(`/v1/assets/${assetUid}/comments`),
  addComment: (assetUid: string, author: string, text: string) => {
    const now = new Date().toISOString();
    return request<AssetComment>(`/v1/assets/${assetUid}/comments`, {
      method: "POST",
      body: json({ uid: crypto.randomUUID(), author, text, created: now, updated: now }),
    });
  },
  tickets: (assetUid: string) =>
    request<AssetTicket[]>(`/v1/assets/${assetUid}/tickets`),
  labels: (assetUid: string) => request<AssetLabel[]>(`/v1/assets/${assetUid}/labels`),
  addLabel: (assetUid: string, input: AssetLabelInput) => {
    const now = new Date().toISOString();
    return request<AssetLabel>(`/v1/assets/${assetUid}/labels`, {
      method: "POST",
      body: json({
        uid: crypto.randomUUID(),
        created_at: now,
        updated_at: now,
        ...input,
      }),
    });
  },
  deleteLabel: (assetUid: string, labelUid: string) =>
    request<void>(`/v1/assets/${assetUid}/labels/${labelUid}`, { method: "DELETE" }),
};

export const labelsApi = {
  search: (query?: { search?: string; type?: string }) => {
    const params = new URLSearchParams();
    if (query?.search) params.set("search", query.search);
    if (query?.type) params.set("type", query.type);
    const qs = params.toString();
    return request<AssetLabelSearchResult[]>(`/v1/labels${qs ? `?${qs}` : ""}`);
  },
};

export const attachmentsApi = {
  list: (assetUid: string) =>
    request<Attachment[]>(`/v1/attachments?asset_uid=${assetUid}`),
  upload: async (assetUid: string, file: File): Promise<Attachment> => {
    const session = await loadSession();
    if (!session) throw new Error("Not signed in");
    const form = new FormData();
    form.append("file", file);
    const resp = await fetch(
      `${session.baseUrl}/v1/attachments?asset_uid=${assetUid}`,
      { method: "POST", headers: authHeaders(session), body: form },
    );
    const data = await resp.json();
    if (!resp.ok) throw new ApiError(resp.status, data);
    return data as Attachment;
  },
  // The download endpoint requires the Bearer header, so a plain <img src=""> /
  // <a href=""> can't hit it directly — fetch as a blob and hand back an object
  // URL the caller is responsible for revoking (URL.revokeObjectURL) when done.
  /** An attachment's content as text — for the SVG sheets of a drawing,
   * which are rendered inline rather than shown through an <img>. */
  fetchText: async (uid: string): Promise<string> => {
    const session = await loadSession();
    if (!session) throw new Error("Not signed in");
    const resp = await fetch(`${session.baseUrl}/v1/attachments/${uid}`, {
      headers: authHeaders(session),
    });
    if (!resp.ok) throw new ApiError(resp.status, await resp.text());
    return resp.text();
  },

  fetchBlobUrl: async (uid: string): Promise<string> => {
    const session = await loadSession();
    if (!session) throw new Error("Not signed in");
    const resp = await fetch(`${session.baseUrl}/v1/attachments/${uid}`, {
      headers: authHeaders(session),
    });
    if (!resp.ok) throw new ApiError(resp.status, await resp.text());
    const blob = await resp.blob();
    return URL.createObjectURL(blob);
  },
  delete: (uid: string) => request<void>(`/v1/attachments/${uid}`, { method: "DELETE" }),
};

/** The shared icon library types are chosen from — upload once, reuse
 * anywhere, unlike an object's avatar or a one-off attachment. */
export const iconsApi = {
  list: () => request<Icon[]>("/v1/icons"),
  upload: async (file: File, name?: string): Promise<Icon> => {
    const session = await loadSession();
    if (!session) throw new Error("Not signed in");
    const form = new FormData();
    form.append("file", file);
    if (name) form.append("name", name);
    const resp = await fetch(`${session.baseUrl}/v1/icons`, {
      method: "POST",
      headers: authHeaders(session),
      body: form,
    });
    const data = await resp.json();
    if (!resp.ok) throw new ApiError(resp.status, data);
    return data as Icon;
  },
  update: (uid: string, input: IconUpdate) =>
    request<Icon>(`/v1/icons/${uid}`, { method: "PUT", body: json(input) }),
  delete: (uid: string) => request<void>(`/v1/icons/${uid}`, { method: "DELETE" }),
  fetchBlobUrl: async (uid: string): Promise<string> => {
    const session = await loadSession();
    if (!session) throw new Error("Not signed in");
    const resp = await fetch(`${session.baseUrl}/v1/icons/${uid}`, {
      headers: authHeaders(session),
    });
    if (!resp.ok) throw new ApiError(resp.status, await resp.text());
    const blob = await resp.blob();
    return URL.createObjectURL(blob);
  },
};

export const globalValuesApi = {
  list: () => request<GlobalValue[]>("/v1/global-values"),
  get: (uid: string) => request<GlobalValue>(`/v1/global-values/${uid}`),
  create: (input: GlobalValueInput) =>
    request<GlobalValue>("/v1/global-values", { method: "POST", body: json(input) }),
  update: (uid: string, input: Partial<GlobalValueInput>) =>
    request<GlobalValue>(`/v1/global-values/${uid}`, { method: "PUT", body: json(input) }),
  delete: (uid: string) => request<void>(`/v1/global-values/${uid}`, { method: "DELETE" }),
};

export const importsApi = {
  list: () => request<ImportJob[]>("/v1/imports"),
  get: (uid: string) => request<ImportJob>(`/v1/imports/${uid}`),
  create: (input: ImportInput) =>
    request<ImportJob>("/v1/imports", { method: "POST", body: json(input) }),
};

export const transfersApi = {
  list: () => request<TransferJob[]>("/v1/transfers"),
  get: (uid: string) => request<TransferJob>(`/v1/transfers/${uid}`),
  create: (input: TransferRequest) =>
    request<TransferJob>("/v1/transfers", { method: "POST", body: json(input) }),
};

export const importConfigsApi = {
  list: () => request<ImportConfig[]>("/v1/import-configs"),
  get: (uid: string) => request<ImportConfig>(`/v1/import-configs/${uid}`),
  create: (input: ImportConfigInput) =>
    request<ImportConfig>("/v1/import-configs", { method: "POST", body: json(input) }),
  update: (uid: string, input: ImportConfigUpdateInput) =>
    request<ImportConfig>(`/v1/import-configs/${uid}`, { method: "PUT", body: json(input) }),
  delete: (uid: string) => request<void>(`/v1/import-configs/${uid}`, { method: "DELETE" }),
  run: (uid: string) =>
    request<ImportConfig>(`/v1/import-configs/${uid}/run`, { method: "POST" }),
};

export const workspacesApi = {
  me: () => request<Me>("/v1/me"),
  listMine: () => request<MyWorkspace[]>("/v1/me/workspaces"),
  /** `id` omitted: the server derives it from the name by the
   * installation's rule, so a stale form cannot make one that breaks it. */
  create: (name: string, id?: string) =>
    request<MyWorkspace>("/v1/workspaces", {
      method: "POST",
      body: json(id ? { name, id } : { name }),
    }),
  suggestId: (name: string) =>
    request<WorkspaceIdSuggestion>(
      `/v1/workspaces/suggest-id?name=${encodeURIComponent(name)}`,
    ),
  idRule: () => request<WorkspaceIdRule>("/v1/workspaces/id-rule"),
  saveIdRule: (input: WorkspaceIdRule) =>
    request<WorkspaceIdRule>("/v1/workspaces/id-rule", {
      method: "PUT",
      body: json(input),
    }),
  get: (workspaceId: string) => request<WorkspaceDetail>(`/v1/workspaces/${workspaceId}`),
  update: (workspaceId: string, input: WorkspaceUpdateInput) =>
    request<Workspace>(`/v1/workspaces/${workspaceId}`, { method: "PUT", body: json(input) }),
  delete: (workspaceId: string) =>
    request<void>(`/v1/workspaces/${workspaceId}`, { method: "DELETE" }),
  integrityReport: (workspaceId: string) =>
    request<IntegrityReport>(`/v1/workspaces/${workspaceId}/integrity-report`),
  relink: (workspaceId: string) =>
    request<{ relink: RelinkResult; report: IntegrityReport }>(
      `/v1/workspaces/${workspaceId}/relink`,
      { method: "POST" },
    ),
  cleanup: (workspaceId: string, options: CleanupOptions) =>
    request<{ cleanup: CleanupResult; report: IntegrityReport }>(
      `/v1/workspaces/${workspaceId}/cleanup`,
      { method: "POST", body: json(options) },
    ),
  setDefaultAccess: (workspaceId: string, input: DefaultAccess) =>
    request<WorkspaceDetail>(`/v1/workspaces/${workspaceId}/default-access`, {
      method: "PUT",
      body: json(input),
    }),
  listMembers: (workspaceId: string) =>
    request<Member[]>(`/v1/workspaces/${workspaceId}/members`),
  upsertMember: (workspaceId: string, input: MemberInput) =>
    request<Member>(`/v1/workspaces/${workspaceId}/members`, { method: "PUT", body: json(input) }),
  removeMember: (workspaceId: string, userId: string) =>
    request<void>(`/v1/workspaces/${workspaceId}/members/${userId}`, { method: "DELETE" }),
  listUsers: () => request<AdminUser[]>("/v1/admin/users"),
  setUserAdmin: (userId: string, isAdmin: boolean) =>
    request<AdminUser>(`/v1/admin/users/${userId}`, {
      method: "PUT",
      body: json({ is_admin: isAdmin }),
    }),
};

export const issueSubresourcesApi = {
  history: (uid: string) => request<IssueHistoryEntry[]>(`/v1/issues/${uid}/history`),
  attachments: (uid: string) => request<Attachment[]>(`/v1/issues/${uid}/attachments`),
  uploadAttachment: async (uid: string, file: File): Promise<Attachment> => {
    const session = await loadSession();
    if (!session) throw new Error("Not signed in");
    const form = new FormData();
    form.append("file", file);
    const resp = await fetch(`${session.baseUrl}/v1/issues/${uid}/attachments`, {
      method: "POST",
      headers: authHeaders(session),
      body: form,
    });
    const data = await resp.json();
    if (!resp.ok) throw new ApiError(resp.status, data);
    return data as Attachment;
  },
};

export const issueLinksApi = {
  list: (uid: string) => request<IssueLinks>(`/v1/issues/${uid}/links`),
  linkAsset: (uid: string, assetUid: string, relation = "affects") =>
    request<IssueAssetLink>(`/v1/issues/${uid}/links/assets`, {
      method: "POST",
      body: json({ asset_uid: assetUid, relation }),
    }),
  unlinkAsset: (uid: string, assetUid: string) =>
    request<void>(`/v1/issues/${uid}/links/assets/${assetUid}`, { method: "DELETE" }),
  linkTicket: (uid: string, issueUid: string, relation = "relates") =>
    request<IssueTicketLink>(`/v1/issues/${uid}/links/tickets`, {
      method: "POST",
      body: json({ issue_uid: issueUid, relation }),
    }),
  unlinkTicket: (uid: string, linkId: number) =>
    request<void>(`/v1/issues/${uid}/links/tickets/${linkId}`, { method: "DELETE" }),
  linkDocument: (uid: string, documentUid: string, relation = "documents") =>
    request<IssueDocumentLink>(`/v1/issues/${uid}/links/documents`, {
      method: "POST",
      body: json({ document_uid: documentUid, relation }),
    }),
  unlinkDocument: (uid: string, relationId: number) =>
    request<void>(`/v1/issues/${uid}/links/documents/${relationId}`, { method: "DELETE" }),
};

export const membersApi = {
  directory: () => request<MemberDirectoryEntry[]>("/v1/members"),
};

export const documentsApi = {
  list: (documentTypeUid?: string) =>
    request<AppDocument[]>(`/v1/documents${documentTypeUid ? `?document_type_uid=${documentTypeUid}` : ""}`),
  get: (uid: string) => request<AppDocument>(`/v1/documents/${uid}`),
  create: (input: DocumentInput) =>
    request<AppDocument>("/v1/documents", { method: "POST", body: json(input) }),
  update: (uid: string, input: DocumentUpdateInput) =>
    request<AppDocument>(`/v1/documents/${uid}`, { method: "PUT", body: json(input) }),
  delete: (uid: string) => request<void>(`/v1/documents/${uid}`, { method: "DELETE" }),
  bulkDelete: (uids: string[]) =>
    request<BulkDeleteResult>("/v1/documents/bulk-delete", { method: "POST", body: json({ uids }) }),
  retire: (uid: string, reason: string) =>
    request<AppDocument>(`/v1/documents/${uid}/retire`, { method: "POST", body: json({ reason }) }),
  current: (uid: string) => request<DocumentRevision>(`/v1/documents/${uid}/current`),
  retention: (uid: string) => request<RetentionView>(`/v1/documents/${uid}/retention`),
  setRetention: (uid: string, retention_class: RetentionClass) =>
    request<RetentionView>(`/v1/documents/${uid}/retention`, { method: "PUT", body: json({ retention_class }) }),
  supersede: (uid: string, by_document_uid: string, reason: string) =>
    request<AppDocument>(`/v1/documents/${uid}/supersede`, { method: "POST", body: json({ by_document_uid, reason }) }),
  verifyAttachment: (attachmentUid: string) => request<AttachmentCheck>(`/v1/attachments/${attachmentUid}/verify`),

  listRevisions: (uid: string) => request<DocumentRevision[]>(`/v1/documents/${uid}/revisions`),
  createRevision: (uid: string, input: DocumentRevisionInput) =>
    request<DocumentRevision>(`/v1/documents/${uid}/revisions`, { method: "POST", body: json(input) }),
  getRevision: (uid: string, revUid: string) =>
    request<DocumentRevision>(`/v1/documents/${uid}/revisions/${revUid}`),
  updateRevision: (uid: string, revUid: string, input: DocumentRevisionInput) =>
    request<DocumentRevision>(`/v1/documents/${uid}/revisions/${revUid}`, {
      method: "PUT",
      body: json(input),
    }),
  submitRevision: (uid: string, revUid: string) =>
    request<DocumentRevision>(`/v1/documents/${uid}/revisions/${revUid}/submit`, { method: "POST" }),
  approveRevision: (uid: string, revUid: string, comment?: string) =>
    request<DocumentRevision>(`/v1/documents/${uid}/revisions/${revUid}/approve`, {
      method: "POST",
      body: json({ comment }),
    }),
  rejectRevision: (uid: string, revUid: string, comment: string) =>
    request<DocumentRevision>(`/v1/documents/${uid}/revisions/${revUid}/reject`, {
      method: "POST",
      body: json({ comment }),
    }),
  publishRevision: (uid: string, revUid: string) =>
    request<DocumentRevision>(`/v1/documents/${uid}/revisions/${revUid}/publish`, { method: "POST" }),

  listRelations: (uid: string) => request<DocumentRelation[]>(`/v1/documents/${uid}/relations`),
  addRelation: (
    uid: string,
    input: { to_type: DocumentRelation["to_type"]; to_uid: string; relation_type: string },
  ) => request<DocumentRelation>(`/v1/documents/${uid}/relations`, { method: "POST", body: json(input) }),
  removeRelation: (uid: string, relationId: number) =>
    request<void>(`/v1/documents/${uid}/relations/${relationId}`, { method: "DELETE" }),

  /** Move a batch of documents onto one type. */
  retype: (uids: string[], documentTypeUid: string | null) =>
    request<RetypeResult>("/v1/documents/retype", {
      method: "POST",
      body: json({ uids, document_type_uid: documentTypeUid }),
    }),

  /** Markdown files (and the images they use) as documents. */
  importMarkdown: async (
    files: File[],
    documentTypeUid: string | null,
  ): Promise<MarkdownImportResult> => {
    const session = await loadSession();
    if (!session) throw new Error("Not signed in");
    const form = new FormData();
    for (const file of files) {
      // A folder picker knows the path inside the folder; a plain multi-file
      // input does not. Sending the path when there is one is what lets
      // `images/layout.png` in a body find the file it names.
      const path = (file as File & { webkitRelativePath?: string }).webkitRelativePath;
      form.append("files", file, path || file.name);
    }
    if (documentTypeUid) form.append("document_type_uid", documentTypeUid);
    const resp = await fetch(`${session.baseUrl}/v1/documents/import`, {
      method: "POST",
      headers: authHeaders(session),
      body: form,
    });
    const data = await resp.json();
    if (!resp.ok) throw new ApiError(resp.status, data);
    return data as MarkdownImportResult;
  },

  listRevisionAttachments: (uid: string, revUid: string) =>
    request<Attachment[]>(`/v1/documents/${uid}/revisions/${revUid}/attachments`),
  uploadRevisionAttachment: async (
    uid: string,
    revUid: string,
    file: File,
  ): Promise<Attachment> => {
    const session = await loadSession();
    if (!session) throw new Error("Not signed in");
    const form = new FormData();
    form.append("file", file);
    const resp = await fetch(
      `${session.baseUrl}/v1/documents/${uid}/revisions/${revUid}/attachments`,
      { method: "POST", headers: authHeaders(session), body: form },
    );
    const data = await resp.json();
    if (!resp.ok) throw new ApiError(resp.status, data);
    return data as Attachment;
  },
};

export const rolesApi = {
  list: () => request<Role[]>("/v1/roles"),
  listBindings: (workspaceId: string) =>
    request<RoleBinding[]>(`/v1/workspaces/${workspaceId}/bindings`),
  createBinding: (workspaceId: string, input: RoleBindingInput) =>
    request<RoleBinding>(`/v1/workspaces/${workspaceId}/bindings`, {
      method: "POST",
      body: json(input),
    }),
  deleteBinding: (workspaceId: string, bindingId: number) =>
    request<void>(`/v1/workspaces/${workspaceId}/bindings/${bindingId}`, { method: "DELETE" }),
  myPermissions: (workspaceId: string) =>
    request<EffectivePermissions>(`/v1/workspaces/${workspaceId}/my-permissions`),
};

export const directoryApi = {
  groups: (search?: string) =>
    request<DirectoryGroup[]>(`/v1/groups${search ? `?search=${encodeURIComponent(search)}` : ""}`),
  groupMembers: (uid: string) => request<DirectoryGroupMember[]>(`/v1/groups/${uid}/members`),
  status: () => request<DirectoryStatus>("/v1/directory/status"),
  sync: () => request<Record<string, unknown>>("/v1/directory/sync", { method: "POST" }),
};

export const graphApi = {
  summary: () => request<GraphSummary>("/v1/graph/summary"),
  walk: (params: {
    kind: string;
    uid: string;
    depth: number;
    kinds?: string[];
    maxNodes?: number;
  }) => {
    const query = new URLSearchParams({
      kind: params.kind,
      uid: params.uid,
      depth: String(params.depth),
    });
    if (params.kinds?.length) query.set("kinds", params.kinds.join(","));
    if (params.maxNodes) query.set("max_nodes", String(params.maxNodes));
    return request<Graph>(`/v1/graph?${query.toString()}`);
  },
};

export const attributeValuesApi = {
  /** Every value an indexed attribute already holds in this workspace —
   * the vocabulary offered as you type. */
  list: (appliesTo: "objects" | "tickets" | "documents", key: string) =>
    request<string[]>(
      `/v1/attribute-values?applies_to=${appliesTo}&key=${encodeURIComponent(key)}&limit=200`,
    ),
};

export const aiApi = {
  getConfig: () => request<LLMConfig | null>("/v1/ai/config"),
  saveConfig: (input: LLMConfigInput) =>
    request<LLMConfig>("/v1/ai/config", { method: "PUT", body: json(input) }),
  deleteConfig: () => request<void>("/v1/ai/config", { method: "DELETE" }),
  check: () => request<LLMCheckResult>("/v1/ai/config/check", { method: "POST" }),
  /** What the application asks before offering an AI action. */
  status: () => request<AIStatus>("/v1/ai/status"),

  suggestDocumentTypes: (onlyUntyped: boolean, limit: number) =>
    request<SuggestRunResult>("/v1/ai/suggest/document-types", {
      method: "POST",
      body: json({ only_untyped: onlyUntyped, limit }),
    }),
  suggestions: (status = "proposed") =>
    request<AISuggestion[]>(`/v1/ai/suggestions?status=${status}`),
  accept: (ids: number[]) =>
    request<{ applied: number; skipped: number[] }>("/v1/ai/suggestions/accept", {
      method: "POST",
      body: json({ ids }),
    }),
  draftDocument: (input: {
    title: string;
    document_type_uid?: string | null;
    notes?: string;
  }) => request<DraftDocumentResult>("/v1/ai/draft-document", {
    method: "POST",
    body: json(input),
  }),
  reviewDocument: (input: {
    title: string;
    document_type_uid?: string | null;
    body_markdown: string;
  }) => request<ReviewDocumentResult>("/v1/ai/review-document", {
    method: "POST",
    body: json(input),
  }),
  draftTicket: (input: { title: string; description: string }) =>
    request<DraftTicketResult>("/v1/ai/draft-ticket", {
      method: "POST",
      body: json(input),
    }),

  /** What is in this photograph, as a draft for the new-object form. */
  identifyObject: async (file: File): Promise<PhotoIdentification> => {
    const session = await loadSession();
    if (!session) throw new Error("Not signed in");
    const form = new FormData();
    form.append("file", file);
    const resp = await fetch(`${session.baseUrl}/v1/ai/identify-object`, {
      method: "POST",
      headers: authHeaders(session),
      body: form,
    });
    const data = await resp.json();
    if (!resp.ok) throw new ApiError(resp.status, data);
    return data as PhotoIdentification;
  },

  /** A question answered from this workspace's records, with its working. */
  ask: (question: string) =>
    request<AskResult>("/v1/ai/ask", { method: "POST", body: json({ question }) }),

  reject: (ids: number[]) =>
    request<{ rejected: number; skipped: number[] }>("/v1/ai/suggestions/reject", {
      method: "POST",
      body: json({ ids }),
    }),
};

/** The unified knowledge layer: one object's whole context, one search across
 * assets, tickets and documents, and the operations cockpit. */
export const hubApi = {
  search: (q: string, limit = 8) =>
    request<HubSearchResult>(`/v1/hub/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  overview: () => request<HubOverview>("/v1/hub/overview"),
  assetContext: (uid: string) => request<AssetContext>(`/v1/hub/assets/${uid}/context`),
  ticketContext: (uid: string) => request<TicketContext>(`/v1/hub/tickets/${uid}/context`),
  documentContext: (uid: string) => request<DocumentContext>(`/v1/hub/documents/${uid}/context`),
};

/** The fact ledger: review queue, provenance, decisions and installation
 * history. Every change here is a decision recorded in the audit ledger. */
export const ledgerApi = {
  review: () => request<ReviewQueue>("/v1/ledger/review"),
  queues: () => request<QueueDashboard>("/v1/ledger/review/queues"),
  escalateReview: () =>
    request<{ backup: number; governance: number; without_recipient: number }>("/v1/ledger/review/escalate", { method: "POST" }),
  facts: (uid: string) => request<RecordFacts>(`/v1/ledger/records/${uid}/facts`),
  decide: (batch: LedgerDecision[]) =>
    request<{ decisions: string[] }>("/v1/ledger/decisions", { method: "POST", body: json({ batch }) }),
  edit: (uid: string, input: { predicate: string; value?: unknown; member?: unknown; present?: boolean; reason?: string }) =>
    request<{ ok: boolean }>(`/v1/ledger/records/${uid}/edit`, { method: "POST", body: json(input) }),
  approveRevision: (revisionId: string) =>
    request<{ state: string }>(`/v1/ledger/revisions/${revisionId}/approve`, { method: "POST" }),
  rejectRevision: (revisionId: string) =>
    request<{ state: string }>(`/v1/ledger/revisions/${revisionId}/reject`, { method: "POST" }),
  installations: (query: { position_uid?: string; asset_uid?: string; at?: string }) => {
    const q = new URLSearchParams(Object.entries(query).filter(([, v]) => v) as [string, string][]);
    return request<InstallationView[]>(`/v1/installations?${q.toString()}`);
  },
  confirmInstallation: (uid: string, validFrom?: TemporalValue) =>
    request<{ ok: boolean }>(`/v1/installations/${uid}/confirm`, {
      method: "POST",
      body: json(validFrom ? { valid_from: validFrom } : {}),
    }),
  rejectInstallation: (uid: string) =>
    request<{ ok: boolean }>(`/v1/installations/${uid}/reject`, { method: "POST" }),
  swap: (input: { position_uid: string; new_asset_uid: string; at: string; precision?: string; reason?: string }) =>
    request<{ ended: string[]; installation_uid: string }>("/v1/installations/swap", {
      method: "POST",
      body: json(input),
    }),
  accessPoint: (uid: string) =>
    request<{ access_point: AccessPointView; address_history: AccessPointView[] }>(`/v1/access-points/${uid}`),
  whoUsed: (address: string, at: string) =>
    request<{ access_points: AccessPointView[]; used_by: AddressUse[] }>(
      `/v1/access-points?${new URLSearchParams({ address, at }).toString()}`,
    ),
  reassign: (uid: string, input: { position_uid: string; at: TemporalValue }) =>
    request<AccessPointView>(`/v1/access-points/${uid}/reassign`, { method: "POST", body: json(input) }),
  segmentPort: (uid: string) => request<SegmentPort>(`/v1/ledger/segments/${uid}/port`),
  confirmPortMap: (uid: string, input: { installation_uid: string; port_uid: string }) =>
    request<SegmentPort>(`/v1/ledger/segments/${uid}/port-map`, { method: "POST", body: json(input) }),
  ticketLinks: (ticketUid: string) => request<TicketLinkView[]>(`/v1/ledger/tickets/${ticketUid}/links`),
  recordTickets: (uid: string) => request<RecordTickets>(`/v1/ledger/records/${uid}/tickets`),
  rules: () => request<{ rules: RuleEntry[]; check: string[] }>("/v1/ledger/rules"),
  streams: () => request<{ id: string; kind: string; frozen_at: string | null }[]>("/v1/ledger/streams"),
  merge: (input: { survivor_uid: string; loser_uid: string; reason?: string }) =>
    request<{ decision_id: string }>("/v1/ledger/identity/merge", { method: "POST", body: json(input) }),
  dismissCandidate: (input: { records: string[]; kind: "reject_candidate" | "confirm_new"; reason?: string }) =>
    request<{ decision_id: string }>("/v1/ledger/identity/dismiss", { method: "POST", body: json(input) }),
  lookup: (identifier: string) => request<LookupHit>(`/v1/lookup/${encodeURIComponent(identifier)}`),
};

export const equipmentApi = {
  get: (uid: string) => request<EquipmentState>(`/v1/equipment/${uid}`),
  setLifecycle: (uid: string, state: string, reason?: string) =>
    request<unknown>(`/v1/equipment/${uid}/lifecycle`, { method: "POST", body: json({ state, reason }) }),
  setCustody: (uid: string, custodian: string, reason?: string) =>
    request<ValueHistory>(`/v1/equipment/${uid}/custody`, { method: "POST", body: json({ custodian, reason }) }),
  positionSpares: (uid: string) =>
    request<{ basis: Record<string, string> | null; spares: SpareView[] }>(`/v1/equipment/positions/${uid}/spares`),
};

export const bulkApi = {
  list: () => request<BulkChangeView[]>("/v1/bulk-changes"),
  get: (id: string) => request<BulkChangeView>(`/v1/bulk-changes/${id}`),
  preview: (spec: Record<string, unknown>, description?: string) =>
    request<BulkChangeView>("/v1/bulk-changes", { method: "POST", body: json({ spec, description }) }),
  apply: (id: string) => request<BulkChangeView>(`/v1/bulk-changes/${id}/apply`, { method: "POST" }),
  approve: (id: string) => request<BulkChangeView>(`/v1/bulk-changes/${id}/approve`, { method: "POST" }),
  undo: (id: string) => request<BulkChangeView>(`/v1/bulk-changes/${id}/undo`, { method: "POST" }),
};

export const auditApi = {
  trail: (uid: string) => request<AuditEntry[]>(`/v1/ledger/records/${uid}/audit`),
  digests: () => request<AuditDigestView[]>("/v1/ledger/audit/digests"),
  verify: () => request<{ ok: boolean; day?: string; reason?: string; days?: number; head?: string }>("/v1/ledger/audit/verify"),
  seal: () => request<{ day: string; digest: string }>("/v1/ledger/audit/seal", { method: "POST" }),
  unmerge: (merge_decision_id: string, reason?: string) =>
    request<{ decision_id: string }>("/v1/ledger/identity/unmerge", { method: "POST", body: json({ merge_decision_id, reason }) }),
};

export const workflowApi = {
  transitions: (uid: string) => request<TicketTransitions>(`/v1/issues/${uid}/transitions`),
  transition: (uid: string, input: { to: string; comment?: string; resolution?: string; assignee?: string }) =>
    request<Issue>(`/v1/issues/${uid}/transition`, { method: "POST", body: json(input) }),
  watchers: (uid: string) => request<string[]>(`/v1/issues/${uid}/watchers`),
  watch: (uid: string, user?: string) =>
    request<string[]>(`/v1/issues/${uid}/watchers`, { method: "POST", body: json(user ? { user } : {}) }),
  unwatch: (uid: string, user: string) =>
    request<void>(`/v1/issues/${uid}/watchers/${encodeURIComponent(user)}`, { method: "DELETE" }),
  list: () => request<{ workflows: WorkflowDef[]; builtin: WorkflowDef; default: string | null }>("/v1/workflows"),
  create: (def: Omit<WorkflowDef, "uid">) => request<WorkflowDef>("/v1/workflows", { method: "POST", body: json(def) }),
  importJira: (definition: unknown, is_default = false) =>
    request<WorkflowDef>("/v1/workflows/import-jira", { method: "POST", body: json({ definition, is_default }) }),
  bind: (uid: string, schema_uid: string) =>
    request<{ ok: boolean }>(`/v1/workflows/${uid}/bind`, { method: "POST", body: json({ schema_uid }) }),
  rehearsal: (uid: string) => request<Rehearsal>(`/v1/workflows/${uid}/rehearsal`),
  escalate: () => request<{ escalated: number }>("/v1/workflows/escalate", { method: "POST" }),
  notifications: (unread = false) =>
    request<NotificationView[]>(`/v1/notifications${unread ? "?unread=true" : ""}`),
  readNotification: (id: number) => request<{ ok: boolean }>(`/v1/notifications/${id}/read`, { method: "POST" }),
  readAll: () => request<{ ok: boolean }>("/v1/notifications/read-all", { method: "POST" }),
};

export const accessReviewsApi = {
  templates: () => request<RoleTemplate[]>("/v1/access-reviews/templates"),
  installTemplates: () => request<{ added: string[] }>("/v1/access-reviews/templates", { method: "POST" }),
  list: () => request<AccessReviewView[]>("/v1/access-reviews"),
  get: (id: string) => request<AccessReviewView>(`/v1/access-reviews/${id}`),
  create: (required_signers = 2) =>
    request<AccessReviewView>("/v1/access-reviews", { method: "POST", body: json({ required_signers }) }),
  sign: (id: string, input: { signer?: string; comment?: string }) =>
    request<AccessReviewView>(`/v1/access-reviews/${id}/sign`, { method: "POST", body: json(input) }),
};

export const legacyMigrationApi = {
  list: () => request<MigrationPlanView[]>("/v1/migration/plans"),
  get: (id: string) => request<MigrationPlanView>(`/v1/migration/plans/${id}`),
  plan: (inventory_workspace_id?: string) =>
    request<MigrationPlanView>("/v1/migration/plans", { method: "POST", body: json({ inventory_workspace_id }) }),
  override: (id: string, item: number, outcome: string, reason: string) =>
    request<MigrationRow>(`/v1/migration/plans/${id}/items/${item}/override`, { method: "POST", body: json({ outcome, reason }) }),
  apply: (id: string) => request<MigrationPlanView>(`/v1/migration/plans/${id}/apply`, { method: "POST" }),
  rollback: (id: string) => request<MigrationPlanView>(`/v1/migration/plans/${id}/rollback`, { method: "POST", body: json({}) }),
  finalize: (id: string, golden_waiver?: string) =>
    request<MigrationPlanView>(`/v1/migration/plans/${id}/finalize`, { method: "POST", body: json({ golden_waiver }) }),
  golden: () => request<GoldenIncident[]>("/v1/migration/golden-incidents"),
  addGolden: (input: { name: string; symptoms: string[]; expected_causes: string[]; symptom_kind?: Record<string, string> }) =>
    request<GoldenIncident>("/v1/migration/golden-incidents", { method: "POST", body: json(input) }),
  removeGolden: (id: string) => request<void>(`/v1/migration/golden-incidents/${id}`, { method: "DELETE" }),
  runGolden: () => request<GoldenRun>("/v1/migration/golden-incidents/run", { method: "POST" }),
  verify: (id: string) => request<MigrationPlanView>(`/v1/migration/plans/${id}/verify`, { method: "POST" }),
  gate: () => request<{ ok: boolean; blocked: string[]; mixed_open: string[]; unplanned: number }>("/v1/migration/gate"),
  /** The decision report as CSV (§12.5), as a download URL. */
  reportUrl: async (id: string): Promise<string> => {
    const session = await loadSession();
    if (!session) throw new Error("Not signed in");
    const resp = await fetch(`${session.baseUrl}/v1/migration/plans/${id}/report.csv`, { headers: authHeaders(session) });
    if (!resp.ok) throw new ApiError(resp.status, await resp.text());
    return URL.createObjectURL(await resp.blob());
  },
};

export const retirementApi = {
  status: () => request<RetirementStatus>("/v1/retirement"),
  recordRetention: (input: { reference: string; jira_archive_until: string; exports_until?: string; audit_until?: string; note?: string }) =>
    request<{ decision_id: string }>("/v1/retirement/retention", { method: "POST", body: json(input) }),
  sign: (attestations: Record<string, boolean>, reason?: string) =>
    request<RetirementStatus>("/v1/retirement/sign", { method: "POST", body: json({ attestations, reason }) }),
};

export const domainsApi = {
  list: () => request<DomainView[]>("/v1/domains"),
  get: (id: string) => request<DomainDetail>(`/v1/domains/${encodeURIComponent(id)}`),
  create: (input: { id: string; name: string; resource: string; stream_ids: string[]; pilot: boolean; archive_url?: string }) =>
    request<DomainView>("/v1/domains", { method: "POST", body: json(input) }),
  stage: (id: string, stage: string) =>
    request<DomainView>(`/v1/domains/${encodeURIComponent(id)}/stage`, { method: "POST", body: json({ stage }) }),
  freeze: (id: string, watermark: unknown, manifest: unknown, attestations: Record<string, boolean> = {},
           waivers: Record<string, string> = {}) =>
    request<DomainView>(`/v1/domains/${encodeURIComponent(id)}/freeze`, {
      method: "POST",
      body: json({ watermark, manifest, attestations, waivers }),
    }),
  setStewards: (id: string, steward: string, backup: string) =>
    request<DomainView>(`/v1/domains/${encodeURIComponent(id)}/stewards`, { method: "PUT", body: json({ steward, backup }) }),
  reconcile: (id: string, manifest: unknown) =>
    request<ReconciliationBody & { id: string }>(`/v1/domains/${encodeURIComponent(id)}/reconcile`, {
      method: "POST",
      body: json({ manifest }),
    }),
  explain: (id: string, difference: string, reason: string) =>
    request<{ decision_id: string }>(`/v1/domains/${encodeURIComponent(id)}/explain`, {
      method: "POST",
      body: json({ difference, reason }),
    }),
  reversionExport: (id: string) =>
    request<Record<string, unknown> & { sha256: string }>(`/v1/domains/${encodeURIComponent(id)}/reversion-export`, {
      method: "POST",
    }),
  revert: (id: string, reason: string) =>
    request<DomainView>(`/v1/domains/${encodeURIComponent(id)}/revert`, { method: "POST", body: json({ reason }) }),
  exit: (id: string, attestations: Record<string, boolean>) =>
    request<DomainView>(`/v1/domains/${encodeURIComponent(id)}/exit`, { method: "POST", body: json({ attestations }) }),
};
