import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { workspacesApi } from "../../api/client";
import type { WorkspaceIdRule } from "../../api/types";

/** Settings that belong to the installation rather than to a workspace.
 *
 * One so far: how a workspace's identifier is derived from its name. It is
 * a setting rather than a constant because the prefix is a local
 * convention — another INFN site would want its own, and hard-coding this
 * one would make this installation's habits everyone's.
 */

/** The same rule as the server's, for the preview only. The server derives
 * the identifier it actually assigns; this just shows the shape while
 * somebody is choosing, so a wrong preview costs nothing. */
function preview(name: string, rule: WorkspaceIdRule): string {
  const separator = (rule.separator || "-").slice(0, 1);
  let slug = name
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/ß/g, "ss")
    .replace(/[^A-Za-z0-9]+/g, separator);
  const edge = new RegExp(`^\\${separator}+|\\${separator}+$`, "g");
  slug = slug.replace(edge, "");
  if (rule.case === "lower") slug = slug.toLowerCase();
  if (rule.case === "upper") slug = slug.toUpperCase();
  if (rule.prefix && !slug.startsWith(rule.prefix)) slug = `${rule.prefix}${slug}`;
  return slug.slice(0, rule.max_length || 40).replace(edge, "");
}

const EXAMPLES = ["Divisione Acceleratori", "EUAPS", "BTF / Beam Test Facility"];

export function AdminSettings() {
  const queryClient = useQueryClient();
  const stored = useQuery({ queryKey: ["workspace-id-rule"], queryFn: workspacesApi.idRule });

  const [rule, setRule] = useState<WorkspaceIdRule>({
    prefix: "",
    separator: "-",
    case: "lower",
    max_length: 40,
  });
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (loaded || !stored.data) return;
    setRule(stored.data);
    setLoaded(true);
  }, [stored.data, loaded]);

  const save = useMutation({
    mutationFn: () => workspacesApi.saveIdRule(rule),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspace-id-rule"] });
      queryClient.invalidateQueries({ queryKey: ["workspace-id-suggestion"] });
    },
  });

  const set = (patch: Partial<WorkspaceIdRule>) => setRule((r) => ({ ...r, ...patch }));

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold text-slate-900">Administration settings</h1>
      <p className="mt-1 text-sm text-slate-500">
        Settings that apply to the whole installation, not to one workspace.
      </p>

      <section className="mt-8">
        <h2 className="text-sm font-semibold text-slate-900">Workspace identifiers</h2>
        <p className="mt-1 text-sm text-slate-500">
          How a new workspace's id is derived from its name. The id goes into URLs, PAT
          tokens and the object keys imports derive, and it can't be changed afterwards —
          so it's worth one rule rather than whatever each admin types. Existing
          workspaces are unaffected.
        </p>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-sm font-medium text-slate-700">Prefix</label>
            <input
              value={rule.prefix}
              onChange={(e) => set({ prefix: e.target.value })}
              placeholder="e.g. lnf-"
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2 font-mono text-sm"
            />
            <p className="mt-1 text-xs text-slate-500">
              Added unless the name already starts with it. Leave blank for none.
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">Between words</label>
            <select
              value={rule.separator}
              onChange={(e) => set({ separator: e.target.value })}
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="-">Hyphen ( - )</option>
              <option value="_">Underscore ( _ )</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">Letter case</label>
            <select
              value={rule.case}
              onChange={(e) => set({ case: e.target.value as WorkspaceIdRule["case"] })}
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="lower">lowercase</option>
              <option value="upper">UPPERCASE</option>
              <option value="keep">Leave as typed</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">Maximum length</label>
            <input
              type="number"
              min={4}
              max={120}
              value={rule.max_length}
              onChange={(e) => set({ max_length: Number(e.target.value) })}
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
        </div>

        <div className="mt-5 rounded border border-slate-200 bg-slate-50 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            With this rule
          </p>
          <dl className="mt-2 space-y-1">
            {EXAMPLES.map((example) => (
              <div key={example} className="flex items-baseline gap-2 text-sm">
                <dt className="text-slate-600">{example}</dt>
                <dd className="text-slate-400">→</dd>
                <dd className="font-mono text-slate-800">{preview(example, rule)}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-2 text-xs text-slate-500">
            An id already taken gets a number added, so two workspaces with the same name
            both work.
          </p>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <button
            type="button"
            onClick={() => save.mutate()}
            disabled={save.isPending}
            className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {save.isPending ? "Saving…" : "Save rule"}
          </button>
          {save.isSuccess && <span className="text-sm text-emerald-700">Saved.</span>}
          {save.isError && (
            <span className="text-sm text-red-600">Could not save the rule.</span>
          )}
        </div>
      </section>
    </div>
  );
}
