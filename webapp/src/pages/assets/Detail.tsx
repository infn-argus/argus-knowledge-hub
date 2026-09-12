import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  assetSubresourcesApi,
  assetsApi,
  attachmentsApi,
  membersApi,
  relationsApi,
  schemasApi,
} from "../../api/client";
import { LABEL_ISSUERS, LABEL_TYPES } from "../../api/types";
import { AttributeValue } from "../../components/AttributeValue";
import { AuthenticatedImage } from "../../components/AuthenticatedImage";
import { RelationGraph } from "../../components/RelationGraph";
import { effectiveAttributes, inheritedKeys } from "../../lib/schemaAttributes";

function SectionCard({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
        {action}
      </div>
      <div className="mt-3">{children}</div>
    </div>
  );
}

async function downloadAttachment(uid: string, filename: string) {
  const url = await attachmentsApi.fetchBlobUrl(uid);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function AssetDetail() {
  const { uid } = useParams<{ uid: string }>();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [commentText, setCommentText] = useState("");
  const [commentAuthor, setCommentAuthor] = useState("web-user");
  const [relationTarget, setRelationTarget] = useState("");
  const [relationType, setRelationType] = useState("related_to");
  const [showGraph, setShowGraph] = useState(false);
  const [labelType, setLabelType] = useState<string>(LABEL_TYPES[0]);
  const [labelValue, setLabelValue] = useState("");
  const [labelIssuer, setLabelIssuer] = useState<string>(LABEL_ISSUERS[0]);

  const asset = useQuery({
    queryKey: ["assets", uid],
    queryFn: () => assetsApi.get(uid!),
    enabled: !!uid,
  });
  const schema = useQuery({
    queryKey: ["schemas", asset.data?.schema_uid],
    queryFn: () => schemasApi.get(asset.data!.schema_uid),
    enabled: !!asset.data,
  });
  const allSchemas = useQuery({ queryKey: ["schemas"], queryFn: schemasApi.list });
  const allAssets = useQuery({ queryKey: ["assets"], queryFn: () => assetsApi.list() });
  const members = useQuery({ queryKey: ["members"], queryFn: membersApi.directory });
  const relations = useQuery({ queryKey: ["relations"], queryFn: relationsApi.list });
  const attachments = useQuery({
    queryKey: ["attachments", uid],
    queryFn: () => attachmentsApi.list(uid!),
    enabled: !!uid,
  });
  const history = useQuery({
    queryKey: ["asset-history", uid],
    queryFn: () => assetSubresourcesApi.history(uid!),
    enabled: !!uid,
  });
  const comments = useQuery({
    queryKey: ["asset-comments", uid],
    queryFn: () => assetSubresourcesApi.comments(uid!),
    enabled: !!uid,
  });
  const tickets = useQuery({
    queryKey: ["asset-tickets", uid],
    queryFn: () => assetSubresourcesApi.tickets(uid!),
    enabled: !!uid,
  });
  const labels = useQuery({
    queryKey: ["asset-labels", uid],
    queryFn: () => assetSubresourcesApi.labels(uid!),
    enabled: !!uid,
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => attachmentsApi.upload(uid!, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["attachments", uid] }),
  });
  const deleteAttachmentMutation = useMutation({
    mutationFn: attachmentsApi.delete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["attachments", uid] }),
  });
  const addCommentMutation = useMutation({
    mutationFn: () => assetSubresourcesApi.addComment(uid!, commentAuthor, commentText),
    onSuccess: () => {
      setCommentText("");
      queryClient.invalidateQueries({ queryKey: ["asset-comments", uid] });
    },
  });
  const addRelationMutation = useMutation({
    mutationFn: () => relationsApi.create(uid!, relationTarget, relationType),
    onSuccess: () => {
      setRelationTarget("");
      queryClient.invalidateQueries({ queryKey: ["relations"] });
      queryClient.invalidateQueries({ queryKey: ["assets", uid] });
    },
  });
  const deleteRelationMutation = useMutation({
    mutationFn: relationsApi.delete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["relations"] }),
  });
  const addLabelMutation = useMutation({
    mutationFn: () =>
      assetSubresourcesApi.addLabel(uid!, {
        type: labelType,
        value: labelValue,
        issuer: labelIssuer,
      }),
    onSuccess: () => {
      setLabelValue("");
      queryClient.invalidateQueries({ queryKey: ["asset-labels", uid] });
    },
  });
  const deleteLabelMutation = useMutation({
    mutationFn: (labelUid: string) => assetSubresourcesApi.deleteLabel(uid!, labelUid),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["asset-labels", uid] }),
  });

  if (asset.isLoading) return <p className="text-sm text-slate-500">Loading…</p>;
  if (!asset.data) return <p className="text-sm text-red-600">Asset not found.</p>;

  const a = asset.data;
  const attrDefs = effectiveAttributes(schema.data, allSchemas.data);
  const inherited = inheritedKeys(schema.data, attrDefs);
  const assetName = (id: string) => allAssets.data?.find((x) => x.uid === id)?.name ?? id;
  const outbound = relations.data?.filter((r) => r.from_asset_uid === a.uid) ?? [];
  const inbound = relations.data?.filter((r) => r.to_asset_uid === a.uid) ?? [];
  const visibleAttachments = attachments.data?.filter((att) => att.uid !== a.avatar_icon_uid) ?? [];

  return (
    <div>
      {showGraph && <RelationGraph assetUid={a.uid} onClose={() => setShowGraph(false)} />}

      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          {a.avatar_icon_uid && (
            <AuthenticatedImage
              uid={a.avatar_icon_uid}
              alt={a.name}
              className="h-16 w-16 rounded object-cover"
            />
          )}
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-semibold text-slate-900">
              {a.name}
              {a.is_global && (
                <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs font-medium text-amber-700">
                  Global
                </span>
              )}
            </h1>
            <p className="text-sm text-slate-500">
              {a.key} · {a.type} · schema:{" "}
              <Link to={`/schemas/${a.schema_uid}`} className="hover:underline">
                {schema.data?.name ?? a.schema_uid}
              </Link>
            </p>
          </div>
        </div>
        <Link
          to={`/assets/${a.uid}/edit`}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          Edit
        </Link>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <SectionCard title="Attributes">
          {attrDefs.length === 0 ? (
            <p className="text-sm text-slate-400">This schema has no attributes defined.</p>
          ) : (
            <dl className="space-y-1.5 text-sm">
              {attrDefs.map((attr) => (
                <div key={attr.id ?? attr.name} className="flex justify-between gap-4">
                  <dt className="text-slate-500">
                    {attr.name}
                    {inherited.has(attr.key ?? attr.name) && (
                      <span className="ml-1 text-[10px] uppercase tracking-wide text-slate-400">
                        inherited
                      </span>
                    )}
                  </dt>
                  <dd className="text-right text-slate-900">
                    <AttributeValue
                      attribute={attr}
                      value={a.attributes[attr.key ?? attr.name]}
                      assets={allAssets.data}
                      members={members.data}
                    />
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </SectionCard>

        <SectionCard
          title="Relations"
          action={
            (outbound.length > 0 || inbound.length > 0) && (
              <button
                onClick={() => setShowGraph(true)}
                className="text-xs text-indigo-600 hover:text-indigo-800"
              >
                View graph
              </button>
            )
          }
        >
          <div className="space-y-3 text-sm">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Outbound {outbound.length > 0 && `(${outbound.length})`}
              </p>
              {outbound.length === 0 && <p className="text-slate-400">None</p>}
              {outbound.map((r) => (
                <div key={r.id} className="flex items-center justify-between">
                  <span>
                    {r.relation_type} →{" "}
                    <Link to={`/assets/${r.to_asset_uid}`} className="hover:underline">
                      {assetName(r.to_asset_uid)}
                    </Link>
                  </span>
                  <button
                    onClick={() => deleteRelationMutation.mutate(r.id)}
                    className="text-xs text-red-500 hover:text-red-700"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Inbound {inbound.length > 0 && `(${inbound.length})`}
              </p>
              {inbound.length === 0 && <p className="text-slate-400">None</p>}
              {inbound.map((r) => (
                <div key={r.id} className="flex items-center justify-between">
                  <span>
                    <Link to={`/assets/${r.from_asset_uid}`} className="hover:underline">
                      {assetName(r.from_asset_uid)}
                    </Link>{" "}
                    → {r.relation_type}
                  </span>
                  <button
                    onClick={() => deleteRelationMutation.mutate(r.id)}
                    className="text-xs text-red-500 hover:text-red-700"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (relationTarget) addRelationMutation.mutate();
            }}
            className="mt-3 flex gap-2"
          >
            <select
              value={relationTarget}
              onChange={(e) => setRelationTarget(e.target.value)}
              className="flex-1 rounded border border-slate-300 px-2 py-1 text-xs"
            >
              <option value="">Target asset…</option>
              {allAssets.data
                ?.filter((x) => x.uid !== a.uid)
                .map((x) => (
                  <option key={x.uid} value={x.uid}>
                    {x.name}
                  </option>
                ))}
            </select>
            <input
              value={relationType}
              onChange={(e) => setRelationType(e.target.value)}
              className="w-28 rounded border border-slate-300 px-2 py-1 text-xs"
            />
            <button
              type="submit"
              className="rounded bg-slate-900 px-3 py-1 text-xs text-white hover:bg-slate-800"
            >
              Add
            </button>
          </form>
        </SectionCard>

        <SectionCard
          title="Attachments"
          action={
            <button
              onClick={() => fileInputRef.current?.click()}
              className="text-xs text-slate-600 hover:text-slate-900"
            >
              + Upload
            </button>
          }
        >
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) uploadMutation.mutate(file);
              e.target.value = "";
            }}
          />
          <ul className="space-y-1 text-sm">
            {visibleAttachments.map((att) => (
              <li key={att.uid} className="flex items-center justify-between">
                <span className="truncate">
                  {att.filename}{" "}
                  <span className="text-xs text-slate-400">
                    ({att.file_size ? `${Math.round(att.file_size / 1024)} KB` : "?"})
                  </span>
                </span>
                <span className="flex shrink-0 gap-3">
                  <button
                    onClick={() => downloadAttachment(att.uid, att.filename)}
                    className="text-xs text-indigo-600 hover:text-indigo-800"
                  >
                    Download
                  </button>
                  <button
                    onClick={() => deleteAttachmentMutation.mutate(att.uid)}
                    className="text-xs text-red-500 hover:text-red-700"
                  >
                    Delete
                  </button>
                </span>
              </li>
            ))}
            {visibleAttachments.length === 0 && (
              <p className="text-slate-400">No attachments.</p>
            )}
          </ul>
        </SectionCard>

        <SectionCard title="Linked tickets">
          <ul className="space-y-1 text-sm">
            {tickets.data?.map((t) => (
              <li key={t.uid} className="flex justify-between">
                <span>
                  {t.ticket_key}: {t.summary}
                </span>
                <span className="text-xs text-slate-400">{t.status}</span>
              </li>
            ))}
            {tickets.data?.length === 0 && (
              <p className="text-slate-400">No linked tickets.</p>
            )}
          </ul>
        </SectionCard>

        <SectionCard title="Labels">
          <ul className="space-y-1 text-sm">
            {labels.data?.map((l) => (
              <li key={l.uid} className="flex items-center justify-between">
                <span>
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
                    {l.type}
                  </span>{" "}
                  {l.value}
                  {l.verified && (
                    <span className="ml-1 text-xs text-green-600">verified</span>
                  )}
                </span>
                <button
                  onClick={() => deleteLabelMutation.mutate(l.uid)}
                  className="text-xs text-red-500 hover:text-red-700"
                >
                  Remove
                </button>
              </li>
            ))}
            {labels.data?.length === 0 && <p className="text-slate-400">No labels yet.</p>}
          </ul>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (labelValue.trim()) addLabelMutation.mutate();
            }}
            className="mt-3 flex gap-2"
          >
            <select
              value={labelType}
              onChange={(e) => setLabelType(e.target.value)}
              className="rounded border border-slate-300 px-2 py-1 text-xs"
            >
              {LABEL_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <input
              value={labelValue}
              onChange={(e) => setLabelValue(e.target.value)}
              placeholder="Value"
              className="flex-1 rounded border border-slate-300 px-2 py-1 text-xs"
            />
            <select
              value={labelIssuer}
              onChange={(e) => setLabelIssuer(e.target.value)}
              className="rounded border border-slate-300 px-2 py-1 text-xs"
            >
              {LABEL_ISSUERS.map((i) => (
                <option key={i} value={i}>
                  {i}
                </option>
              ))}
            </select>
            <button
              type="submit"
              className="rounded bg-slate-900 px-3 py-1 text-xs text-white hover:bg-slate-800"
            >
              Add
            </button>
          </form>
        </SectionCard>

        <SectionCard title="History">
          <ul className="space-y-2 text-sm">
            {history.data?.map((h) => (
              <li key={h.uid} className="border-l-2 border-slate-200 pl-2">
                <p className="text-slate-900">
                  {h.type} — <span className="text-slate-500">{h.author}</span>
                </p>
                <p className="text-xs text-slate-400">
                  {new Date(h.timestamp).toLocaleString()}
                </p>
              </li>
            ))}
            {history.data?.length === 0 && <p className="text-slate-400">No history yet.</p>}
          </ul>
        </SectionCard>

        <SectionCard title="Comments">
          <ul className="space-y-2 text-sm">
            {comments.data?.map((c) => (
              <li key={c.uid}>
                <p className="text-slate-900">{c.text}</p>
                <p className="text-xs text-slate-400">
                  {c.author} · {new Date(c.created).toLocaleString()}
                </p>
              </li>
            ))}
            {comments.data?.length === 0 && <p className="text-slate-400">No comments yet.</p>}
          </ul>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (commentText.trim()) addCommentMutation.mutate();
            }}
            className="mt-3 space-y-2"
          >
            <input
              value={commentAuthor}
              onChange={(e) => setCommentAuthor(e.target.value)}
              className="w-full rounded border border-slate-300 px-2 py-1 text-xs"
              placeholder="Your name"
            />
            <textarea
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
              rows={2}
              className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
              placeholder="Add a comment…"
            />
            <button
              type="submit"
              className="rounded bg-slate-900 px-3 py-1 text-xs text-white hover:bg-slate-800"
            >
              Comment
            </button>
          </form>
        </SectionCard>
      </div>
    </div>
  );
}
