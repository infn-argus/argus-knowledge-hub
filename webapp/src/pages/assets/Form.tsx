import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { assetsApi, intakeApi, schemasApi, type AssistResult } from "../../api/client";
import { AttributeInput } from "../../components/AttributeInput";
import { finalFor, GuidedEntry } from "../../components/GuidedEntry";
import { effectiveAttributes } from "../../lib/schemaAttributes";

export function AssetForm() {
  const { uid } = useParams<{ uid: string }>();
  const isEditing = !!uid;
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const schemas = useQuery({ queryKey: ["schemas"], queryFn: schemasApi.list });
  const existing = useQuery({
    queryKey: ["assets", uid],
    queryFn: () => assetsApi.get(uid!),
    enabled: isEditing,
  });

  const [schemaUid, setSchemaUid] = useState(searchParams.get("schema_uid") ?? "");
  const [name, setName] = useState("");
  const [key, setKey] = useState("");
  const [type, setType] = useState("");
  const [attributes, setAttributes] = useState<Record<string, unknown>>({});
  const [isGlobal, setIsGlobal] = useState(false);
  const [assisted, setAssisted] = useState<AssistResult | null>(null);
  const draft = { uid: uid ?? null, schema_uid: schemaUid, name, key, type, attributes };

  /** Values from the checklist or the assistant, by field name. */
  const apply = (values: Record<string, unknown>) => {
    for (const [field, value] of Object.entries(values)) {
      if (field === "schema_uid") setSchemaUid(String(value ?? ""));
      else if (field === "name") setName(String(value ?? ""));
      else if (field === "key") setKey(String(value ?? ""));
      else if (field.startsWith("attributes.")) {
        const k = field.slice(11);
        setAttributes((prev) => ({ ...prev, [k]: value }));
      }
    }
  };

  useEffect(() => {
    if (existing.data) {
      setSchemaUid(existing.data.schema_uid);
      setName(existing.data.name);
      setKey(existing.data.key);
      setType(existing.data.type);
      setAttributes(existing.data.attributes);
      setIsGlobal(existing.data.is_global);
    }
  }, [existing.data]);

  const objectSchemas = (schemas.data ?? []).filter((s) => (s.applies_to ?? "objects") === "objects");
  const schema = schemas.data?.find((s) => s.uid === schemaUid);
  const attrDefs = effectiveAttributes(schema, schemas.data);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (isEditing) {
        return assetsApi.update(uid!, {
          name, key, type, attributes, schema_uid: schemaUid, is_global: isGlobal,
        });
      }
      return assetsApi.create({
        uid: crypto.randomUUID(),
        schema_uid: schemaUid,
        key,
        name,
        type: type || schema?.name || "Asset",
        attributes,
        is_global: isGlobal,
      });
    },
    onSuccess: async (asset) => {
      // Which suggestions were kept or corrected: provenance, never a blocker.
      if (assisted) {
        await intakeApi.outcome(assisted.run_id, asset!.uid, finalFor(assisted, draft)).catch(() => undefined);
      }
      queryClient.invalidateQueries({ queryKey: ["assets"] });
      navigate(`/assets/${asset!.uid}`);
    },
  });

  return (
    <div className="max-w-6xl">
      <h1 className="text-2xl font-semibold text-slate-900">
        {isEditing ? "Edit asset" : "New asset"}
      </h1>
      {!isEditing && (
        <p className="mt-1 text-sm text-slate-500">
          Describe it or photograph its nameplate, and the form fills itself; the checklist keeps the entry correct.
        </p>
      )}

      <div className="mt-2 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
      <div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          saveMutation.mutate();
        }}
        className="mt-6 space-y-5"
      >
        <div>
          <label className="block text-sm font-medium text-slate-700">Schema</label>
          <select
            value={schemaUid}
            onChange={(e) => setSchemaUid(e.target.value)}
            required
            disabled={isEditing}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100"
          >
            <option value="">Select a schema…</option>
            {objectSchemas.map((s) => (
              <option key={s.uid} value={s.uid}>
                {s.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Key</label>
          <input
            value={key}
            onChange={(e) => setKey(e.target.value)}
            required
            placeholder="Unique identifier, e.g. AST-001"
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Type</label>
          <input
            value={type}
            onChange={(e) => setType(e.target.value)}
            placeholder={schema?.name ?? "Asset"}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="is_global"
            checked={isGlobal}
            onChange={(e) => setIsGlobal(e.target.checked)}
          />
          <label htmlFor="is_global" className="text-sm text-slate-700">
            Global — visible and referenceable from every workspace (for what is meant to be shared: models, vendors, people, companies). Otherwise it stays in this workspace.
          </label>
        </div>

        {attrDefs.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-slate-700">Attributes</label>
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
          disabled={saveMutation.isPending || !schemaUid}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {saveMutation.isPending ? "Saving…" : "Save asset"}
        </button>
        {saveMutation.isError && (
          <p className="text-sm text-red-600">{(saveMutation.error as Error).message}</p>
        )}
      </form>
      </div>
      <aside className="lg:sticky lg:top-4 lg:self-start">
        <GuidedEntry kind="asset" draft={draft} onApply={apply} onAssist={setAssisted} />
      </aside>
      </div>
    </div>
  );
}
