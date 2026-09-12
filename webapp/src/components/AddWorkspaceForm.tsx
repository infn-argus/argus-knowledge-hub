import { FormEvent, useState } from "react";
import { checkHealth, checkToken } from "../api/client";
import { addProfile, Profile, removeProfile } from "../api/session";

const DEFAULT_BASE_URL = "https://assets-api.90.147.174.30.myip.cloud.infn.it";

export function AddWorkspaceForm({
  onAdded,
  existingCount = 0,
}: {
  onAdded: (profile: Profile) => void;
  existingCount?: number;
}) {
  const [name, setName] = useState(existingCount === 0 ? "Default" : "");
  const [baseUrl, setBaseUrl] = useState(DEFAULT_BASE_URL);
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setChecking(true);
    try {
      const trimmedUrl = baseUrl.trim().replace(/\/$/, "");
      const healthy = await checkHealth(trimmedUrl);
      if (!healthy) {
        setError("Could not reach that server URL.");
        return;
      }
      const profile = addProfile(name.trim() || "Workspace", {
        baseUrl: trimmedUrl,
        token: token.trim(),
      });
      const valid = await checkToken();
      if (!valid) {
        setError("Server reachable, but the token was rejected.");
        removeProfile(profile.id);
        return;
      }
      onAdded(profile);
    } finally {
      setChecking(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-slate-700">Workspace name</label>
        <input
          className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Production"
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700">Server URL</label>
        <input
          className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700">API Token</label>
        <input
          type="password"
          className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="Paste your Bearer token"
          required
        />
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <button
        type="submit"
        disabled={checking}
        className="w-full rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
      >
        {checking ? "Checking…" : existingCount === 0 ? "Sign in" : "Add workspace"}
      </button>
    </form>
  );
}
