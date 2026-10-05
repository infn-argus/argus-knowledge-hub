import { useQuery, useQueryClient } from "@tanstack/react-query";
import { tokensApi } from "../../api/client";
import { TokenTable } from "../../components/ApiTokens";

/** Every API token in the installation, personal and robot, for an administrator to see and revoke. */
export function AdminTokensPage() {
  const queryClient = useQueryClient();
  const tokens = useQuery({ queryKey: ["all-tokens"], queryFn: tokensApi.all });
  const active = (tokens.data ?? []).filter((t) => t.status === "active");
  const ended = (tokens.data ?? []).filter((t) => t.status !== "active");
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["all-tokens"] });
  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">API tokens</h1>
        <p className="mt-1 text-sm text-slate-500">Every personal and robot token in the installation. People make
          their own on <i>My account</i>; workspace owners make robot tokens on the workspace's <i>Robot tokens</i>
          page. Revoking one here stops it at once.</p>
      </div>
      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-slate-900">Active ({active.length})</h2>
        <TokenTable tokens={active} showOwner onRevoke={(t) => void tokensApi.revokeAny(t.id).then(refresh)} />
      </section>
      {ended.length > 0 && (
        <details>
          <summary className="cursor-pointer text-sm font-semibold text-slate-900">Expired or revoked ({ended.length})</summary>
          <div className="mt-2"><TokenTable tokens={ended} showOwner onRevoke={() => undefined} /></div>
        </details>
      )}
    </div>
  );
}
