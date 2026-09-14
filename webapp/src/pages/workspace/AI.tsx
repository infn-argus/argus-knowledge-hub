import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { aiApi } from "../../api/client";

/** Where this workspace's AI features send their requests.
 *
 * Configured here rather than in the deployment because different
 * workspaces are entitled to different gateways — and because a key typed
 * into this form is encrypted at rest without ever travelling through a
 * values file or a chat window to get there.
 */
export function WorkspaceAI() {
  const queryClient = useQueryClient();
  const config = useQuery({ queryKey: ["ai-config"], queryFn: aiApi.getConfig });

  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [embeddingModel, setEmbeddingModel] = useState("");
  const [visionModel, setVisionModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [enabled, setEnabled] = useState(false);
  const [allowConfidential, setAllowConfidential] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (loaded || config.isLoading) return;
    const c = config.data;
    if (c) {
      setBaseUrl(c.base_url);
      setModel(c.model);
      setEmbeddingModel(c.embedding_model ?? "");
      setVisionModel(c.vision_model ?? "");
      setEnabled(c.enabled);
      setAllowConfidential(c.allow_confidential);
    }
    setLoaded(true);
  }, [config.data, config.isLoading, loaded]);

  const save = useMutation({
    mutationFn: () =>
      aiApi.saveConfig({
        base_url: baseUrl.trim(),
        model: model.trim(),
        embedding_model: embeddingModel.trim() || null,
        vision_model: visionModel.trim() || null,
        // Left out entirely when untouched, so saving a model change does
        // not wipe the stored key.
        ...(apiKey ? { api_key: apiKey } : {}),
        enabled,
        allow_confidential: allowConfidential,
      }),
    onSuccess: () => {
      setApiKey("");
      queryClient.invalidateQueries({ queryKey: ["ai-config"] });
      queryClient.invalidateQueries({ queryKey: ["ai-status"] });
    },
  });

  const check = useMutation({
    mutationFn: aiApi.check,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-config"] });
      queryClient.invalidateQueries({ queryKey: ["ai-status"] });
    },
  });

  const saved = config.data;
  const checkResult = check.data;

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold text-slate-900">AI endpoint</h1>
      <p className="mt-1 text-sm text-slate-500">
        Any OpenAI-compatible endpoint. AI features stay unavailable until a check against
        this endpoint passes, so a gateway whose key has since been rotated reads as
        unavailable rather than quietly failing.
      </p>

      <div className="mt-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700">Endpoint URL</label>
          <input
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="https://ai-gateway.example.infn.it/v1"
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700">Model</label>
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="minimax-m27"
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700">
              Embedding model
            </label>
            <input
              value={embeddingModel}
              onChange={(e) => setEmbeddingModel(e.target.value)}
              placeholder="qwen3-embedding-8b"
              className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
            />
            <p className="mt-1 text-xs text-slate-500">
              Optional. Classifying and linking use embeddings where one is available —
              cheaper and steadier than a chat call per record.
            </p>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">Vision model</label>
          <input
            value={visionModel}
            onChange={(e) => setVisionModel(e.target.value)}
            placeholder="gemma-4-31b-it"
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          />
          <p className="mt-1 text-xs text-slate-500">
            Optional, and usually a different model from the one above: a chat model
            answers “not a multimodal model” when shown a photograph. Needed to identify
            equipment from a picture.
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700">
            API key{saved?.has_api_key && " (one is stored — leave blank to keep it)"}
          </label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={saved?.has_api_key ? "••••••••" : "Leave blank if the endpoint needs none"}
            className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <label className="flex items-start gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            className="mt-0.5"
          />
          <span>
            Offer AI features in this workspace
            <span className="block text-xs text-slate-500">
              Suggestions are always proposals — nothing is written to a record without
              somebody accepting it.
            </span>
          </span>
        </label>

        <label className="flex items-start gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={allowConfidential}
            onChange={(e) => setAllowConfidential(e.target.checked)}
            className="mt-0.5"
          />
          <span>
            Send confidential documents too
            <span className="block text-xs text-slate-500">
              Off by default: documents marked <em>riservato</em> are skipped, because where
              their text goes is a decision worth making deliberately.
            </span>
          </span>
        </label>

        <div className="flex items-center gap-3">
          <button
            onClick={() => save.mutate()}
            disabled={!baseUrl.trim() || !model.trim() || save.isPending}
            className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {save.isPending ? "Saving…" : "Save"}
          </button>
          <button
            onClick={() => check.mutate()}
            disabled={!saved || check.isPending}
            className="rounded border border-slate-300 px-4 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
          >
            {check.isPending ? "Checking…" : "Check endpoint"}
          </button>
          {saved && (
            <button
              onClick={() => {
                if (confirm("Remove this AI endpoint? AI features will stop being offered."))
                  aiApi.deleteConfig().then(() => {
                    queryClient.invalidateQueries({ queryKey: ["ai-config"] });
                    queryClient.invalidateQueries({ queryKey: ["ai-status"] });
                    setLoaded(false);
                  });
              }}
              className="text-sm text-red-500 hover:text-red-700"
            >
              Remove
            </button>
          )}
        </div>

        {checkResult && (
          <div
            className={`rounded border p-3 text-sm ${
              checkResult.ok
                ? "border-green-200 bg-green-50 text-green-800"
                : "border-red-200 bg-red-50 text-red-700"
            }`}
          >
            {checkResult.ok
              ? `This endpoint answered, the key was accepted, and it serves ${model}.`
              : checkResult.error}
            {checkResult.models.length > 0 && (
              <details className="mt-2">
                <summary className="cursor-pointer text-xs">
                  {checkResult.models.length} model(s) offered
                </summary>
                <ul className="mt-1 space-y-0.5 text-xs">
                  {checkResult.models.map((m) => (
                    <li key={m}>
                      <button
                        type="button"
                        onClick={() => setModel(m)}
                        className="hover:underline"
                        title="Use this model"
                      >
                        {m}
                      </button>
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}

        {saved && !checkResult && (
          <p className="text-xs text-slate-500">
            {saved.last_checked_at
              ? saved.last_check_ok
                ? `Checked ${new Date(saved.last_checked_at).toLocaleString()} — working.`
                : `Checked ${new Date(saved.last_checked_at).toLocaleString()} — ${saved.last_check_error}`
              : "Not checked since it was last changed."}
          </p>
        )}
      </div>
    </div>
  );
}
