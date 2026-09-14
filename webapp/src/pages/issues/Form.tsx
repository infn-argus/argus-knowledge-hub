import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  assetsApi,
  globalValuesApi,
  issueLinksApi,
  issuesApi,
  membersApi,
  schemasApi,
} from "../../api/client";
import { AssetMultiPicker } from "../../components/AssetMultiPicker";
import { AttributeInput } from "../../components/AttributeInput";
import { LabelInput } from "../../components/LabelInput";
import { UserPicker } from "../../components/UserPicker";
import { effectiveAttributes } from "../../lib/schemaAttributes";

export function IssueForm() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const { uid } = useParams<{ uid: string }>();
  const isEdit = !!uid;

  const existing = useQuery({
    queryKey: ["issues", uid],
    queryFn: () => issuesApi.get(uid!),
    enabled: isEdit,
  });
  const assets = useQuery({ queryKey: ["assets"], queryFn: () => assetsApi.list() });
  const schemas = useQuery({ queryKey: ["schemas"], queryFn: schemasApi.list });
  const members = useQuery({ queryKey: ["members"], queryFn: membersApi.directory });
  const globalValues = useQuery({ queryKey: ["global-values"], queryFn: globalValuesApi.list });
  const priorityOptions =
    globalValues.data?.find((gv) => gv.applies_to === "tickets" && gv.key === "priority")?.options ?? [];
  const ticketSchemas = schemas.data?.filter((s) => s.applies_to === "tickets") ?? [];

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  // A ticket usually concerns more than one object; the first is its
  // subject and the rest are links.
  const initialAssets = searchParams.get("asset_uid");
  const [assetUids, setAssetUids] = useState<string[]>(initialAssets ? [initialAssets] : []);
  const [linkedAtLoad, setLinkedAtLoad] = useState<string[]>([]);
  const [priority, setPriority] = useState("");
  const [assignee, setAssignee] = useState("");
  const [schemaUid, setSchemaUid] = useState(searchParams.get("schema_uid") ?? "");
  const [labels, setLabels] = useState<string[]>([]);
  const labelSuggestions = useQuery({ queryKey: ["issue-labels"], queryFn: issuesApi.labels });
  const [attributes, setAttributes] = useState<Record<string, unknown>>({});



  useEffect(() => {
    const t = existing.data;
    if (!t) return;
    setTitle(t.title);
    setDescription(t.description ?? "");

    setPriority(t.priority ?? "");
    setAssignee(t.assignee ?? "");
    setSchemaUid(t.schema_uid ?? "");
    setLabels(t.labels ?? []);
    setAttributes(t.attributes ?? {});
  }, [existing.data]);

  const existingLinks = useQuery({
    queryKey: ["issue-links", uid],
    queryFn: () => issueLinksApi.list(uid!),
    enabled: isEdit,
  });

  useEffect(() => {
    if (!existingLinks.data) return;
    const uids = existingLinks.data.assets.map((a) => a.asset_uid);
    setAssetUids(uids);
    setLinkedAtLoad(uids);
  }, [existingLinks.data]);

  const schema = ticketSchemas.find((s) => s.uid === schemaUid);
  const attrDefs = effectiveAttributes(schema, schemas.data);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        title,
        description: description || undefined,
        asset_uid: assetUids[0] || undefined,
        priority: priority || undefined,
        assignee: assignee || undefined,
        schema_uid: schemaUid || undefined,
        labels,
        attributes,
      };
      const saved = isEdit
        ? await issuesApi.update(uid!, payload)
        : await issuesApi.create({ uid: crypto.randomUUID(), ...payload });

      // The subject is a column on the ticket; the rest are links, and a
      // removed one has to be unlinked rather than merely dropped here.
      const keep = new Set(assetUids.slice(1));
      for (const assetUid of keep) {
        if (!linkedAtLoad.includes(assetUid)) {
          await issueLinksApi.linkAsset(saved!.uid, assetUid).catch(() => undefined);
        }
      }
      for (const assetUid of linkedAtLoad) {
        if (!assetUids.includes(assetUid)) {
          await issueLinksApi.unlinkAsset(saved!.uid, assetUid).catch(() => undefined);
        }
      }
      return saved;
    },
    onSuccess: (issue) => {
      queryClient.invalidateQueries({ queryKey: ["issues"] });
      if (isEdit) queryClient.invalidateQueries({ queryKey: ["issues", uid] });
      queryClient.invalidateQueries({ queryKey: ["issue-links", uid] });
      navigate(`/tickets/${issue!.uid}`);
    },
  });

  return (
    <div className="max-w-xl">
      <h1 className="text-2xl font-semibold text-slate-900">
        {isEdit ? "Edit ticket" : "New ticket"}
      </h1>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          saveMutation.mutate();
        }}
        className="mt-6 space-y-5"
      >
        <div>
          <label className="block text-sm font-medium text-slate-700">Type</label>
          <select
            value={schemaUid}
            onChange={(e) => {
              setSchemaUid(e.target.value);
              setAttributes({});
            }}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">None / generic ticket</option>
            {ticketSchemas.map((s) => (
              <option key={s.uid} value={s.uid}>
                {s.name}
                {s.is_global ? " (global)" : ""}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Title</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Labels</label>
          <div className="mt-1">
            <LabelInput
              value={labels}
              onChange={setLabels}
              suggestions={labelSuggestions.data ?? []}
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Objects</label>
          <div className="mt-1">
            <AssetMultiPicker
              options={assets.data ?? []}
              value={assetUids}
              onChange={setAssetUids}
            />
          </div>
          {assetUids.length > 0 && !isEdit && (
            <p className="mt-1 text-xs text-slate-500">
              The ticket will appear on these objects, and they on the ticket.
            </p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700">Priority</label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">None</option>
              {priorityOptions.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.value}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">Assignee</label>
            <div className="mt-1 flex">
              <UserPicker
                members={members.data ?? []}
                value={assignee || null}
                onChange={(userId) => setAssignee(userId ?? "")}
              />
            </div>
          </div>
        </div>

        {schema && attrDefs.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-slate-700">
              {schema.name} attributes
            </label>
            <div className="mt-2 space-y-3 rounded border border-slate-200 p-3">
              {attrDefs.map((attr) => (
                <div key={attr.id ?? attr.name}>
                  <label className="block text-xs font-medium text-slate-500">
                    {attr.name}
                    {attr.required && <span className="text-red-500"> *</span>}
                  </label>
                  <div className="mt-1">
                    <AttributeInput
                      attribute={attr}
                      appliesTo="tickets"
                      value={attributes[attr.key ?? attr.name]}
                      onChange={(v) =>
                        setAttributes((prev) => ({ ...prev, [attr.key ?? attr.name]: v }))
                      }
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={saveMutation.isPending}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {saveMutation.isPending ? "Saving…" : isEdit ? "Save changes" : "Create ticket"}
        </button>
      </form>
    </div>
  );
}
