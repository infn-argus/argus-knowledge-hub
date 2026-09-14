import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { importPaths } from "./paths";
import { ApiError, importConfigsApi } from "../../api/client";
import { MergeStrategy, MERGE_STRATEGIES } from "../../api/types";

export function ImportConfigForm() {
  const { uid, workspaceId } = useParams<{ uid: string; workspaceId: string }>();
  const [searchParams] = useSearchParams();
  const isEdit = !!uid;
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const existing = useQuery({
    queryKey: ["import-configs", uid],
    queryFn: () => importConfigsApi.get(uid!),
    enabled: isEdit,
  });

  const [name, setName] = useState("");
  // Opened from a section's Import link, the form starts on that section's
  // source rather than making you pick it again.
  const requestedSource = searchParams.get("source");
  const [source, setSource] = useState<"jira" | "jira-issues" | "confluence" | "git" | "epik8s">(
    requestedSource === "jira-issues" ||
    requestedSource === "confluence" ||
    requestedSource === "git" ||
    requestedSource === "epik8s"
      ? requestedSource
      : "jira",
  );
  const [mergeStrategy, setMergeStrategy] = useState<MergeStrategy>("override");

  const [baseUrl, setBaseUrl] = useState("");
  const [jiraPat, setJiraPat] = useState("");
  const [jiraSchemaId, setJiraSchemaId] = useState("");

  const [jql, setJql] = useState("");
  const [spaceKey, setSpaceKey] = useState("");
  const [cql, setCql] = useState("");
  const [linkAssets, setLinkAssets] = useState(true);

  const [provider, setProvider] = useState<"github" | "gitlab">("github");
  const [repoUrl, setRepoUrl] = useState("");
  const [gitPat, setGitPat] = useState("");
  const [branch, setBranch] = useState("main");
  const [valuesPath, setValuesPath] = useState("deploy/values.yaml");
  const [createMissingNodes, setCreateMissingNodes] = useState(true);

  // params holds whatever the source needs, so values arrive loosely typed.
  const param = (key: string) => {
    const value = existing.data?.params[key];
    return typeof value === "string" ? value : "";
  };

  useEffect(() => {
    if (!existing.data) return;
    setName(existing.data.name);
    setSource(existing.data.source);
    setMergeStrategy(existing.data.merge_strategy);
    if (existing.data.source === "jira") {
      setBaseUrl(param("base_url"));
      setJiraSchemaId(param("jira_schema_id"));
    } else if (existing.data.source === "confluence") {
      setBaseUrl(param("base_url"));
      setSpaceKey(param("space_key"));
      setCql(param("cql"));
      setLinkAssets(existing.data.params.link_assets !== false);
    } else if (existing.data.source === "jira-issues") {
      setBaseUrl(param("base_url"));
      setJql(param("jql"));
      setLinkAssets(existing.data.params.link_assets !== false);
    } else {
      setProvider((param("provider") as "github" | "gitlab") || "github");
      setRepoUrl(param("repo_url"));
      setBranch(param("branch") || "main");
      setValuesPath(param("path") || "deploy/values.yaml");
      setCreateMissingNodes(existing.data.params.create_missing_nodes !== false);
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
          : source === "confluence"
          ? {
              source: "confluence" as const,
              base_url: baseUrl.replace(/\/+$/, ""),
              space_key: spaceKey || undefined,
              cql: cql || undefined,
              link_assets: linkAssets,
              ...(jiraPat ? { pat: jiraPat } : {}),
            }
          : source === "jira-issues"
          ? {
              source: "jira-issues" as const,
              base_url: baseUrl.replace(/\/+$/, ""),
              jql,
              link_assets: linkAssets,
              ...(jiraPat ? { pat: jiraPat } : {}),
            }
          : source === "epik8s"
          ? {
              source: "epik8s" as const,
              provider,
              repo_url: repoUrl,
              branch,
              path: valuesPath,
              create_missing_nodes: createMissingNodes,
              ...(gitPat ? { pat: gitPat } : {}),
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
        navigate(
          running.last_import_job_uid
            ? importPaths.job(workspaceId!, running.last_import_job_uid)
            : importPaths.list(workspaceId!),
        );
      } else {
        navigate(importPaths.list(workspaceId!));
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
        {(["jira", "jira-issues", "confluence", "git", "epik8s"] as const).map((s) => (
          <button
            key={s}
            type="button"
            disabled={isEdit}
            onClick={() => setSource(s)}
            className={`rounded px-4 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50 ${
              source === s ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {s === "jira"
              ? "Jira objects"
              : s === "jira-issues"
                ? "Jira tickets"
                : s === "confluence"
                  ? "Confluence"
                  : s === "git"
                    ? "Git"
                    : "EPIK8s control"}
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

        {source === "jira" || source === "jira-issues" || source === "confluence" ? (
          <>
            <div>
              <label className="block text-sm font-medium text-slate-700">
                {source === "confluence" ? "Confluence server URL" : "Jira server URL"}
              </label>
              <input
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder={
                  source === "confluence"
                    ? "https://wiki.example.org/confluence"
                    : source === "jira-issues"
                      ? "https://issues.example.org/jira"
                      : "https://servicedesk.example.org"
                }
                required
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
              <p className="mt-1 text-xs text-slate-500">
                {source === "confluence"
                  ? "Include the context path if the server has one — Confluence is often published under /confluence or /wiki rather than at the site root. The import checks both."
                  : "Include the context path if the server has one — many Jira installations live under /jira rather than at the site root. The import checks both."}
              </p>
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
            {source === "confluence" ? (
              <>
                <div>
                  <label className="block text-sm font-medium text-slate-700">Space key</label>
                  <input
                    value={spaceKey}
                    onChange={(e) => setSpaceKey(e.target.value)}
                    placeholder="LNF"
                    className="mt-1 w-full rounded border border-slate-300 px-3 py-2 font-mono text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700">
                    Or a CQL query
                  </label>
                  <input
                    value={cql}
                    onChange={(e) => setCql(e.target.value)}
                    placeholder='space = LNF AND label = "procedure"'
                    className="mt-1 w-full rounded border border-slate-300 px-3 py-2 font-mono text-sm"
                  />
                  <p className="mt-1 text-xs text-slate-500">
                    Pages become documents, typed from their labels. Bodies are converted to
                    Markdown; re-importing a page whose version hasn't changed adds no revision.
                  </p>
                </div>
                <label className="flex items-start gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={linkAssets}
                    onChange={(e) => setLinkAssets(e.target.checked)}
                    className="mt-0.5"
                  />
                  <span>
                    Link documents to objects they mention
                    <span className="block text-xs text-slate-500">
                      A page whose text contains an object key (LNFT2-145356) is attached to it.
                    </span>
                  </span>
                </label>
              </>
            ) : source === "jira" ? (
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
            ) : (
              <>
                <div>
                  <label className="block text-sm font-medium text-slate-700">
                    Which issues (JQL)
                  </label>
                  <input
                    value={jql}
                    onChange={(e) => setJql(e.target.value)}
                    placeholder='project = LNF AND updated >= -90d'
                    required
                    className="mt-1 w-full rounded border border-slate-300 px-3 py-2 font-mono text-sm"
                  />
                  <p className="mt-1 text-xs text-slate-500">
                    Any query the token's account can run in Jira. Start narrow — one project,
                    recent issues — and widen once the result looks right.
                  </p>
                </div>
                <label className="flex items-start gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={linkAssets}
                    onChange={(e) => setLinkAssets(e.target.checked)}
                    className="mt-0.5"
                  />
                  <span>
                    Link tickets to objects they mention
                    <span className="block text-xs text-slate-500">
                      A ticket whose text contains an object key (LNFT2-145356) is attached to
                      that object.
                    </span>
                  </span>
                </label>
              </>
            )}
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
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
              <p className="mt-1 text-xs text-slate-500">
                {isEdit
                  ? "Leave blank to keep whatever is saved."
                  : "Leave blank for a public repository — no token is sent at all, rather than an empty one."}
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Branch</label>
              <input
                value={branch}
                onChange={(e) => setBranch(e.target.value)}
                className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>

            {source === "epik8s" && (
              <>
                <div>
                  <label className="block text-sm font-medium text-slate-700">
                    Path to the beamline configuration
                  </label>
                  <input
                    value={valuesPath}
                    onChange={(e) => setValuesPath(e.target.value)}
                    placeholder="deploy/values.yaml"
                    className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
                  />
                  <p className="mt-1 text-xs text-slate-500">
                    One beamline per configuration. Read only — the file in git deploys
                    the accelerator, and each imported object records the revision it
                    came from.
                  </p>
                </div>
                <label className="flex items-start gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={createMissingNodes}
                    onChange={(e) => setCreateMissingNodes(e.target.checked)}
                    className="mt-0.5"
                  />
                  <span>
                    Create an object for an address nothing in the inventory carries
                    <span className="block text-xs text-slate-500">
                      Addresses are matched to equipment you already hold — a terminal
                      server is linked, not duplicated. The rest become Access Points
                      marked as needing confirmation. Unchecked, they are only listed in
                      the import's warnings.
                    </span>
                  </span>
                </label>
              </>
            )}
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
