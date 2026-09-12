import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ApiError, importConfigsApi } from "../../api/client";
import { MergeStrategy, MERGE_STRATEGIES } from "../../api/types";

export function ImportConfigForm() {
  const { uid } = useParams<{ uid: string }>();
  const isEdit = !!uid;
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const existing = useQuery({
    queryKey: ["import-configs", uid],
    queryFn: () => importConfigsApi.get(uid!),
    enabled: isEdit,
  });

  const [name, setName] = useState("");
  const [source, setSource] = useState<"jira" | "git">("jira");
  const [mergeStrategy, setMergeStrategy] = useState<MergeStrategy>("override");

  const [baseUrl, setBaseUrl] = useState("");
  const [jiraPat, setJiraPat] = useState("");
  const [jiraSchemaId, setJiraSchemaId] = useState("");

  const [provider, setProvider] = useState<"github" | "gitlab">("github");
  const [repoUrl, setRepoUrl] = useState("");
  const [gitPat, setGitPat] = useState("");
  const [branch, setBranch] = useState("main");

  useEffect(() => {
    if (!existing.data) return;
    setName(existing.data.name);
    setSource(existing.data.source);
    setMergeStrategy(existing.data.merge_strategy);
    if (existing.data.source === "jira") {
      setBaseUrl(existing.data.params.base_url ?? "");
      setJiraSchemaId(existing.data.params.jira_schema_id ?? "");
    } else {
      setProvider((existing.data.params.provider as "github" | "gitlab") ?? "github");
      setRepoUrl(existing.data.params.repo_url ?? "");
      setBranch(existing.data.params.branch ?? "main");
    }
  }, [existing.data]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const config =
        source === "jira"
          ? {
              source: "jira" as const,
              base_url: baseUrl.replace(/\/+$/, ""),
              jira_schema_id: jiraSchemaId,
              ...(jiraPat ? { pat: jiraPat } : {}),
            }
          : {
              source: "git" as const,
              provider,
              repo_url: repoUrl,
              branch,
              ...(gitPat ? { pat: gitPat } : {}),
            };
      if (isEdit) {
        return importConfigsApi.update(uid!, { name, merge_strategy: mergeStrategy, config });
      }
      return importConfigsApi.create({ name, merge_strategy: mergeStrategy, config });
    },
    onSuccess: async (saved) => {
      queryClient.invalidateQueries({ queryKey: ["import-configs"] });
      if (!isEdit) {
        // First save also runs it immediately — reuse it later via "Run" on the list.
        const running = await importConfigsApi.run(saved.uid);
        navigate(`/imports/${running.last_import_job_uid}`);
      } else {
        navigate("/imports");
      }
    },
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    saveMutation.mutate();
  };

  if (isEdit && existing.isLoading) {
    return <p className="text-sm text-slate-500">Loading…</p>;
  }

  return (
    <div className="max-w-lg">
      <h1 className="text-2xl font-semibold text-slate-900">
        {isEdit ? "Edit import configuration" : "New import configuration"}
      </h1>
      <p className="mt-1 text-sm text-slate-500">
        Saved once, then re-run any time with one click from the Imports list. Existing
        schemas/assets are matched by key — the merge strategy below controls what happens
        when a match is found.
      </p>

      <div className="mt-6 flex gap-2">
        {(["jira", "git"] as const).map((s) => (
          <button
            key={s}
            type="button"
            disabled={isEdit}
            onClick={() => setSource(s)}
            className={`rounded px-4 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50 ${
              source === s ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {s === "jira" ? "Jira" : "Git"}
          </button>
        ))}
      </div>

      <form onSubmit={submit} className="mt-6 space-y-5">
        <div>
          <label className="block text-sm font-medium text-slate-700">Configuration name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Nightly Jira sync"
            required
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        {source === "jira" ? (
          <>
            <div>
              <label className="block text-sm font-medium text-slate-700">Jira server URL</label>
              <input
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://servicedesk.example.org"
                required
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">
                Personal access token{isEdit && " (leave blank to keep the saved one)"}
              </label>
              <input
                type="password"
                value={jiraPat}
                onChange={(e) => setJiraPat(e.target.value)}
                required={!isEdit}
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Object schema ID</label>
              <input
                value={jiraSchemaId}
                onChange={(e) => setJiraSchemaId(e.target.value)}
                placeholder="32"
                required
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
          </>
        ) : (
          <>
            <div>
              <label className="block text-sm font-medium text-slate-700">Provider</label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value as "github" | "gitlab")}
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="github">GitHub</option>
                <option value="gitlab">GitLab</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Repository URL</label>
              <input
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/owner/repo"
                required
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">
                Personal access token{isEdit && " (leave blank to keep the saved one)"}
              </label>
              <input
                type="password"
                value={gitPat}
                onChange={(e) => setGitPat(e.target.value)}
                required={!isEdit}
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Branch</label>
              <input
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
          </>
        )}

        <div>
          <label className="block text-sm font-medium text-slate-700">
            When a matching object already exists
          </label>
          <select
            value={mergeStrategy}
            onChange={(e) => setMergeStrategy(e.target.value as MergeStrategy)}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          >
            {MERGE_STRATEGIES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-slate-400">
            {MERGE_STRATEGIES.find((s) => s.value === mergeStrategy)?.description}
          </p>
          {mergeStrategy === "remove_all_before" && (
            <p className="mt-1 text-xs font-medium text-red-600">
              Deletes everything previously imported from this source in this workspace before
              every run. This cannot be undone.
            </p>
          )}
        </div>

        {saveMutation.isError && (
          <p className="text-sm text-red-600">
            {saveMutation.error instanceof ApiError
              ? JSON.stringify(saveMutation.error.body)
              : "Failed to save configuration"}
          </p>
        )}

        <button
          type="submit"
          disabled={saveMutation.isPending}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
        >
          {saveMutation.isPending
            ? "Saving…"
            : isEdit
              ? "Save changes"
              : "Save and run now"}
        </button>
      </form>
    </div>
  );
}
