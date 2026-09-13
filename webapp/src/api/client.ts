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
  DocumentInput,
  DocumentUpdateInput,
  DocumentRevision,
  DocumentRevisionInput,
  DocumentRelation,
  GlobalValue,
  GlobalValueInput,
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
  Relation,
  Workspace,
  WorkspaceUpdateInput,
  SchemaInput,
  WorkspaceDetail,
} from "./types";

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
  create: (id: string, name: string) =>
    request<MyWorkspace>("/v1/workspaces", { method: "POST", body: json({ id, name }) }),
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
  retire: (uid: string, reason: string) =>
    request<AppDocument>(`/v1/documents/${uid}/retire`, { method: "POST", body: json({ reason }) }),
  current: (uid: string) => request<DocumentRevision>(`/v1/documents/${uid}/current`),

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
};
