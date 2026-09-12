import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { globalValuesApi } from "../../api/client";
import { ATTRIBUTE_TYPES } from "../../api/types";

export function GlobalValueForm() {
  const { uid } = useParams<{ uid: string }>();
  const isEditing = !!uid;
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const existing = useQuery({
    queryKey: ["global-values", uid],
    queryFn: () => globalValuesApi.get(uid!),
    enabled: isEditing,
  });

  const [name, setName] = useState("");
  const [key, setKey] = useState("");
  const [type, setType] = useState<string>("enumeration");
  const [appliesTo, setAppliesTo] = useState<"objects" | "tickets" | "documents">("objects");
  const [optionsText, setOptionsText] = useState("");

  useEffect(() => {
    if (existing.data) {
      setName(existing.data.name);
      setKey(existing.data.key);
      setType(existing.data.type);
      setAppliesTo(existing.data.applies_to);
      setOptionsText((existing.data.options ?? []).map((o) => o.value).join(", "));
    }
  }, [existing.data]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const options =
        type === "enumeration"
          ? optionsText
              .split(",")
              .map((v) => v.trim())
              .filter(Boolean)
              .map((v) => ({ id: v.toLowerCase().replace(/\s+/g, "_"), value: v }))
          : undefined;
      if (isEditing) {
        return globalValuesApi.update(uid!, { name, key, type, applies_to: appliesTo, options });
      }
      return globalValuesApi.create({
        uid: crypto.randomUUID(), name, key, type, applies_to: appliesTo, options,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["global-values"] });
      navigate("/global-values");
    },
  });

  return (
    <div className="max-w-lg">
      <h1 className="text-2xl font-semibold text-slate-900">
        {isEditing ? "Edit global value" : "New global value"}
      </h1>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          saveMutation.mutate();
        }}
        className="mt-6 space-y-5"
      >
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
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700">Context</label>
          <select
            value={appliesTo}
            onChange={(e) => setAppliesTo(e.target.value as "objects" | "tickets" | "documents")}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="objects">Assets</option>
            <option value="tickets">Tickets</option>
            <option value="documents">Documents</option>
          </select>
          <p className="mt-1 text-xs text-slate-400">
            The same name/key is allowed to exist independently in each context.
          </p>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700">Type</label>
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          >
            {ATTRIBUTE_TYPES.filter((t) => t !== "user" && t !== "current_user").map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
        {type === "enumeration" && (
          <div>
            <label className="block text-sm font-medium text-slate-700">
              Options (comma-separated)
            </label>
            <input
              value={optionsText}
              onChange={(e) => setOptionsText(e.target.value)}
              placeholder="Open, In Progress, Closed"
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
        )}
        <button
          type="submit"
          disabled={saveMutation.isPending}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {saveMutation.isPending ? "Saving…" : "Save"}
        </button>
      </form>
    </div>
  );
}
