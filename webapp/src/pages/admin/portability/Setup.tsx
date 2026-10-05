import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { portabilityApi, problemText } from "../../../api/client";
import type { PortabilityConfig, PortabilitySetup, SetupRepository } from "../../../api/portabilityTypes";
import { ActionButton } from "./shared";
import { ProblemWithStepUp } from "./StepUp";

/** Administration → Portability → Set-up: Git repositories (GitHub, GitLab, any server, or one copied onto
 *  this installation), this installation's signing key, and the keys an import trusts — registered here,
 *  next to whatever the deployment configures, which stays read-only. ARGUS makes the SSH deploy key and
 *  shows only its public half; a token is written once and never shown again. */
export function Setup({ c }: { c: PortabilityConfig }) {
  const setup = useQuery({ queryKey: ["portability-setup"], queryFn: portabilityApi.setup });
  if (setup.isLoading) return <p className="text-sm text-slate-500">Loading…</p>;
  if (setup.isError) return <p className="text-sm text-rose-700">{problemText(setup.error)}</p>;
  const s = setup.data!;
  return (
    <div className="space-y-6">
      {!s.enabled && (
        <div className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Setting up portability from the web app is <b>switched off</b> on this installation
          (<code>ARGUS_PORTABILITY_UI_CONFIG=off</code>): repositories and keys come only from the deployment's
          settings. What is listed below was registered before and is not used.
        </div>
      )}
      {s.enabled && s.separation_of_duties && (
        <p className="text-sm text-slate-600">
          The policy separates duties: what you register here waits for <b>another administrator</b> to approve it.
        </p>
      )}
      <Repositories s={s} />
      <Stores s={s} />
      <SigningKey s={s} c={c} />
      <TrustedKeys s={s} c={c} />
    </div>
  );
}

function useRefresh() {
  const qc = useQueryClient();
  return () => {
    void qc.invalidateQueries({ queryKey: ["portability-setup"] });
    void qc.invalidateQueries({ queryKey: ["portability-config"] });
  };
}

function Section({ title, children, intro }: { title: string; intro?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
      {intro && <div className="mt-1 text-xs text-slate-500">{intro}</div>}
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Copy({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <div className="flex items-start gap-2">
      <code className="block min-w-0 flex-1 break-all rounded bg-slate-50 px-2 py-1 text-[11px] text-slate-700">{text}</code>
      <button type="button" className="shrink-0 rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50"
              onClick={() => { void navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 1500); }}>
        {done ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

function Pending({ kind, id, by }: { kind: "repository" | "trusted_key" | "signing_key" | "store"; id: string; by: string }) {
  const refresh = useRefresh();
  const approve = useMutation({ mutationFn: () => portabilityApi.approveSetup(kind, id), onSuccess: refresh });
  return (
    <span className="inline-flex items-center gap-2 text-xs text-amber-800">
      waiting for approval (registered by {by})
      <ActionButton label="Approve" busy={approve.isPending} onClick={() => approve.mutate()}
                    confirm="Approve it? You cannot approve what you registered yourself." />
      {approve.isError && <ProblemWithStepUp error={approve.error} />}
    </span>
  );
}

// ------------------------------------------------------------------------------ repositories

const FINGERPRINTS: Record<string, string> = {
  github: "https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints",
  gitlab: "https://docs.gitlab.com/ee/user/gitlab_com/#ssh-host-keys-fingerprints",
};

function Repositories({ s }: { s: PortabilitySetup }) {
  const [adding, setAdding] = useState(false);
  return (
    <Section
      title="Git repositories"
      intro={<>Where exports are published and imports fetched from. An exporting installation needs write access;
        one that only imports, read access.</>}
    >
      <table className="w-full text-sm">
        <thead className="text-left text-xs text-slate-500">
          <tr><th className="py-1 pr-3">Name</th><th className="py-1 pr-3">Address</th><th className="py-1 pr-3">Access</th>
            <th className="py-1 pr-3">State</th><th className="py-1" /></tr>
        </thead>
        <tbody>
          {s.deployment.repositories.map((n) => (
            <tr key={n} className="border-t border-slate-100 text-slate-600">
              <td className="py-2 pr-3 font-medium">{n}</td>
              <td className="py-2 pr-3 text-xs" colSpan={3}>set by the deployment (read-only here)</td>
              <td />
            </tr>
          ))}
          {s.repositories.map((r) => <RepositoryRow key={r.name} r={r} enabled={s.enabled} />)}
          {s.deployment.repositories.length === 0 && s.repositories.length === 0 && (
            <tr><td colSpan={5} className="py-2 text-xs text-slate-400">No repository yet.</td></tr>
          )}
        </tbody>
      </table>
      {s.enabled && (adding ? <AddRepository onDone={() => setAdding(false)} /> : (
        <button type="button" onClick={() => setAdding(true)}
                className="mt-3 rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800">
          Add a repository
        </button>
      ))}
    </Section>
  );
}

function AddRepository({ onDone }: { onDone: () => void }) {
  const refresh = useRefresh();
  const [name, setName] = useState("escrow");
  const [url, setUrl] = useState("");
  const [token, setToken] = useState("");
  const https = url.trim().startsWith("https://");
  const add = useMutation({
    mutationFn: () => portabilityApi.addRepository({ name: name.trim(), url: url.trim(), token: https ? token || null : null }),
    onSuccess: () => { refresh(); onDone(); },
  });
  return (
    <div className="mt-3 space-y-3 rounded border border-slate-200 bg-slate-50 p-3 text-sm">
      <label className="block">
        <span className="block text-xs font-medium text-slate-600">Name</span>
        <input value={name} onChange={(e) => setName(e.target.value)} className="mt-1 w-56 rounded border border-slate-300 px-2 py-1" />
        <span className="mt-1 block text-xs text-slate-500">How exports and imports refer to it: lower case, e.g. <code>escrow</code>.</span>
      </label>
      <label className="block">
        <span className="block text-xs font-medium text-slate-600">Address</span>
        <input value={url} onChange={(e) => setUrl(e.target.value)} className="mt-1 w-full rounded border border-slate-300 px-2 py-1"
               placeholder="git@github.com:infn-argus/argus-escrow.git" />
        <span className="mt-1 block text-xs text-slate-500">
          SSH (<code>git@github.com:org/repo.git</code>, <code>ssh://git@baltig.infn.it/group/repo.git</code>): ARGUS makes a
          deploy key for it. HTTPS (<code>https://x-access-token@github.com/org/repo.git</code>, or
          <code> https://oauth2@gitlab.example/group/repo.git</code>): give a token below. Or a path on this installation,
          inside its portability area, for a repository copied here.
        </span>
      </label>
      {https && (
        <label className="block">
          <span className="block text-xs font-medium text-slate-600">Token</span>
          <input type="password" value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off"
                 className="mt-1 w-full max-w-md rounded border border-slate-300 px-2 py-1"
                 placeholder="Leave empty for a public repository (read only)" />
          <span className="mt-1 block text-xs text-slate-500">
            GitHub: a fine-grained token with <i>Contents: read and write</i> on this repository. GitLab: a project access
            token with <i>write_repository</i>. Kept encrypted; never shown again.
          </span>
        </label>
      )}
      <div className="flex items-center gap-2">
        <ActionButton label="Register" busy={add.isPending} disabled={!name.trim() || !url.trim()} onClick={() => add.mutate()}
                      confirm="Register this repository? Archives may then be published to it." />
        <button type="button" onClick={onDone} className="text-sm text-slate-500 hover:underline">Cancel</button>
        {add.isError && <ProblemWithStepUp error={add.error} />}
      </div>
    </div>
  );
}

function RepositoryRow({ r, enabled }: { r: SetupRepository; enabled: boolean }) {
  const refresh = useRefresh();
  const [open, setOpen] = useState(!r.usable);
  const [token, setToken] = useState("");
  const m = (fn: () => Promise<unknown>) => useMutation({ mutationFn: fn, onSuccess: refresh });
  const testRead = m(() => portabilityApi.testRepository(r.name, false));
  const testWrite = m(() => portabilityApi.testRepository(r.name, true));
  const rescan = m(() => portabilityApi.readHostKeys(r.name));
  const confirmKeys = m(() => portabilityApi.confirmHostKeys(r.name, r.host_keys.map((k) => k.fingerprint)));
  const replace = m(() => portabilityApi.replaceToken(r.name, token));
  const remove = m(() => portabilityApi.removeRepository(r.name));
  const errors = [testRead, testWrite, rescan, confirmKeys, replace, remove].filter((x) => x.isError);
  const state = r.status === "pending" ? "waiting for approval"
    : r.auth === "ssh" && !r.host_keys_confirmed ? "confirm the server" : r.usable ? "in use" : "not usable";
  return (
    <>
      <tr className="border-t border-slate-100 align-top">
        <td className="py-2 pr-3 font-medium text-slate-900">{r.name}</td>
        <td className="break-all py-2 pr-3 text-xs text-slate-600">{r.url}</td>
        <td className="py-2 pr-3 text-xs text-slate-600">
          {r.auth === "ssh" ? "SSH deploy key" : r.auth === "https" ? "HTTPS token" : r.auth === "none" ? "public (read only)" : "on this installation"}
        </td>
        <td className={`py-2 pr-3 text-xs ${r.usable ? "text-emerald-700" : "text-amber-700"}`}>
          {state}
          {r.last_test && (
            <span className="block text-slate-500">
              tested: read {r.last_test.read ? "✓" : "✕"}{r.last_test.write !== null && <>, write {r.last_test.write ? "✓" : "✕"}</>}
            </span>
          )}
        </td>
        <td className="py-2 text-right">
          <button type="button" onClick={() => setOpen((v) => !v)} className="text-xs text-slate-500 underline">
            {open ? "Hide" : "Details"}
          </button>
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={5} className="pb-4">
            <div className="space-y-3 rounded border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
              {r.status === "pending" && <Pending kind="repository" id={r.name} by={r.created_by} />}
              {r.auth === "ssh" && r.public_key && (
                <div>
                  <p className="font-medium text-slate-800">1. Add this deploy key to the repository</p>
                  <p className="mt-1 text-slate-500">
                    {r.provider === "github" ? <>GitHub: the repository's <i>Settings → Deploy keys → Add deploy key</i>; tick
                      <b> Allow write access</b> if this installation exports to it.</>
                      : r.provider === "gitlab" ? <>GitLab: the project's <i>Settings → Repository → Deploy keys → Add new key</i>;
                        tick <b>Grant write permissions to this key</b> if this installation exports to it.</>
                      : <>Add it to the repository as a deploy key, with write access if this installation exports to it.</>}
                  </p>
                  <div className="mt-1"><Copy text={r.public_key} /></div>
                </div>
              )}
              {r.auth === "ssh" && (
                <div>
                  <p className="font-medium text-slate-800">2. Confirm the server is the right one</p>
                  {r.host_keys.length === 0 ? (
                    <p className="mt-1 text-amber-800">Its host keys could not be read (the server did not answer).</p>
                  ) : (
                    <>
                      <p className="mt-1 text-slate-500">
                        Compare these fingerprints with the ones the provider publishes
                        {FINGERPRINTS[r.provider] && <> (<a className="underline" href={FINGERPRINTS[r.provider]} target="_blank" rel="noreferrer">list</a>)</>}
                        {r.provider === "other" && " (ask the server's administrators)"}; confirm only if they match.
                      </p>
                      <ul className="mt-1 font-mono">
                        {r.host_keys.map((k) => <li key={k.fingerprint}>{k.type} {k.fingerprint}</li>)}
                      </ul>
                    </>
                  )}
                  {enabled && (
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      {!r.host_keys_confirmed && r.host_keys.length > 0 && (
                        <ActionButton label="Confirm the fingerprints" busy={confirmKeys.isPending} onClick={() => confirmKeys.mutate()}
                                      confirm="They match what the provider publishes?" />
                      )}
                      {r.host_keys_confirmed && <span className="text-emerald-700">✓ confirmed and pinned</span>}
                      <button type="button" className="rounded border border-slate-300 px-2 py-1 hover:bg-white"
                              onClick={() => rescan.mutate()} disabled={rescan.isPending}>
                        {rescan.isPending ? "Reading…" : "Read them again"}
                      </button>
                    </div>
                  )}
                </div>
              )}
              {enabled && <EditRepository r={r} />}
              {r.auth === "https" && enabled && (
                <div className="flex flex-wrap items-center gap-2">
                  <span>Token stored; replace it:</span>
                  <input type="password" value={token} onChange={(e) => setToken(e.target.value)} autoComplete="off"
                         className="w-64 rounded border border-slate-300 px-2 py-1" />
                  <ActionButton label="Replace" busy={replace.isPending} disabled={!token.trim()} onClick={() => replace.mutate()}
                                confirm="Replace the token?" />
                </div>
              )}
              {enabled && (
                <div className="flex flex-wrap items-center gap-2 border-t border-slate-200 pt-3">
                  <span className="font-medium text-slate-800">{r.auth === "ssh" ? "3. " : ""}Test it:</span>
                  <button type="button" className="rounded border border-slate-300 px-2 py-1 hover:bg-white"
                          disabled={testRead.isPending || (r.auth === "ssh" && !r.host_keys_confirmed)} onClick={() => testRead.mutate()}>
                    {testRead.isPending ? "Reading…" : "Read"}
                  </button>
                  <button type="button" className="rounded border border-slate-300 px-2 py-1 hover:bg-white"
                          disabled={testWrite.isPending || (r.auth === "ssh" && !r.host_keys_confirmed) || r.auth === "none"}
                          onClick={() => testWrite.mutate()}
                          title="Pushes a branch argus-connection-test and deletes it at once">
                    {testWrite.isPending ? "Writing…" : "Read and write"}
                  </button>
                  {r.last_test?.error && <span className="text-rose-700">{r.last_test.error}</span>}
                  <span className="flex-1" />
                  <ActionButton label="Remove" danger busy={remove.isPending} onClick={() => remove.mutate()}
                                confirm={`Remove ${r.name}? Exports already published there stay where they are.`} />
                </div>
              )}
              {errors.map((x, i) => <p key={i}><ProblemWithStepUp error={x.error} /></p>)}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function EditRepository({ r }: { r: SetupRepository }) {
  const refresh = useRefresh();
  const [editing, setEditing] = useState(false);
  const [url, setUrl] = useState(r.url);
  const [provider, setProvider] = useState(r.provider);
  const save = useMutation({
    mutationFn: () => portabilityApi.updateRepository(r.name, { url: url.trim(), provider }),
    onSuccess: () => { refresh(); setEditing(false); },
  });
  if (!editing) {
    return (
      <button type="button" className="rounded border border-slate-300 px-2 py-1 hover:bg-white" onClick={() => setEditing(true)}>
        Change address or provider
      </button>
    );
  }
  return (
    <div className="space-y-2">
      <input value={url} onChange={(e) => setUrl(e.target.value)} className="w-full rounded border border-slate-300 px-2 py-1" />
      <div className="flex flex-wrap items-center gap-2">
        <select value={provider} onChange={(e) => setProvider(e.target.value as SetupRepository["provider"])}
                className="rounded border border-slate-300 px-2 py-1">
          {(["github", "gitlab", "other", "local"] as const).map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <ActionButton label="Save" busy={save.isPending} onClick={() => save.mutate()}
                      confirm="Save it? A new SSH server must be confirmed again, and under separation of duties the change is approved again." />
        <button type="button" className="text-slate-500 hover:underline" onClick={() => setEditing(false)}>Cancel</button>
        {save.isError && <ProblemWithStepUp error={save.error} />}
      </div>
      <p className="text-slate-500">The kind of access (SSH, HTTPS, or on this installation) stays: to change it, remove the repository and register it again.</p>
    </div>
  );
}

// ------------------------------------------------------------------------------ artifact stores

function Stores({ s }: { s: PortabilitySetup }) {
  const refresh = useRefresh();
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const add = useMutation({ mutationFn: () => portabilityApi.addStore(name.trim(), note.trim()),
                            onSuccess: () => { refresh(); setName(""); setNote(""); } });
  const remove = useMutation({ mutationFn: (n: string) => portabilityApi.removeStore(n), onSuccess: refresh });
  return (
    <Section
      title="Artifact stores"
      intro={<>Where an export's data (records, attachments) is kept when it does not travel in the repository: a directory
        on this installation's portability volume. The importing installation then needs a copy of it, under the same name.
        Simpler: choose <i>In the repository, with the archive</i> when exporting, and no store is needed.</>}
    >
      <ul className="space-y-2 text-sm">
        {s.deployment.stores.map((n) => (
          <li key={n} className="text-slate-600"><b>{n}</b> <span className="text-xs">set by the deployment (read-only here)</span></li>
        ))}
        {s.stores.map((x) => (
          <li key={x.name} className="flex flex-wrap items-center gap-2">
            <b>{x.name}</b> <code className="text-xs text-slate-500">{x.path}</code>
            {x.note && <span className="text-xs text-slate-500">— {x.note}</span>}
            {x.status === "pending" && <Pending kind="store" id={x.name} by={x.created_by} />}
            <span className="flex-1" />
            {s.enabled && (
              <ActionButton label="Remove" danger busy={remove.isPending && remove.variables === x.name}
                            onClick={() => remove.mutate(x.name)}
                            confirm={`Unregister ${x.name}? Its files stay on the volume.`} />
            )}
          </li>
        ))}
        {s.deployment.stores.length === 0 && s.stores.length === 0 && <li className="text-xs text-slate-400">None.</li>}
      </ul>
      {s.enabled && (
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3 text-sm">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name, e.g. vault"
                 className="w-48 rounded border border-slate-300 px-2 py-1" />
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note"
                 className="w-64 rounded border border-slate-300 px-2 py-1" />
          <ActionButton label="Add the store" busy={add.isPending} disabled={!name.trim()} onClick={() => add.mutate()}
                        confirm="Add this artifact store?" />
          {add.isError && <ProblemWithStepUp error={add.error} />}
        </div>
      )}
    </Section>
  );
}

// ------------------------------------------------------------------------------ keys

function SigningKey({ s, c }: { s: PortabilitySetup; c: PortabilityConfig }) {
  const refresh = useRefresh();
  const [principal, setPrincipal] = useState("");
  const generate = useMutation({ mutationFn: () => portabilityApi.generateSigningKey(principal.trim()), onSuccess: refresh });
  const active = s.signing_keys.find((k) => k.status === "active");
  const pending = s.signing_keys.filter((k) => k.status === "pending");
  return (
    <Section
      title="This installation's signing key"
      intro="Every export is signed with it. Give its public line to the installations that import from this one: they add it to their trusted keys."
    >
      {s.deployment.signing_key ? (
        <p className="text-sm text-slate-600">
          Set by the deployment: <b>{c.signing.principal}</b> · <code>{c.signing.key_id}</code> (read-only here).
        </p>
      ) : (
        <div className="space-y-3 text-sm">
          {active ? (
            <div>
              <p className="text-slate-600"><b>{active.principal}</b> · <code>{active.key_id}</code></p>
              <div className="mt-1"><Copy text={active.public_line} /></div>
            </div>
          ) : <p className="text-amber-800">None yet: exports cannot be signed.</p>}
          {pending.map((k) => (
            <div key={k.id} className="space-y-1">
              <p className="text-slate-600">New key <code>{k.key_id}</code>:</p>
              <Pending kind="signing_key" id={k.id} by={k.created_by} />
            </div>
          ))}
          {s.enabled && (
            <div className="flex flex-wrap items-center gap-2">
              <input value={principal} onChange={(e) => setPrincipal(e.target.value)} placeholder="Name, e.g. argus-infn"
                     className="w-56 rounded border border-slate-300 px-2 py-1" />
              <ActionButton label={active ? "Replace the key" : "Make a signing key"} busy={generate.isPending}
                            onClick={() => generate.mutate()}
                            confirm={active ? "Replace it? Installations that import from here will need the new public line."
                              : "Make this installation's signing key?"} />
              {generate.isError && <ProblemWithStepUp error={generate.error} />}
            </div>
          )}
        </div>
      )}
    </Section>
  );
}

function TrustedKeys({ s, c }: { s: PortabilitySetup; c: PortabilityConfig }) {
  const refresh = useRefresh();
  const [line, setLine] = useState("");
  const [note, setNote] = useState("");
  const add = useMutation({ mutationFn: () => portabilityApi.addTrustedKey(line.trim(), note.trim()),
                            onSuccess: () => { refresh(); setLine(""); setNote(""); } });
  const remove = useMutation({ mutationFn: (id: string) => portabilityApi.removeTrustedKey(id), onSuccess: refresh });
  return (
    <Section
      title="Trusted keys"
      intro="An import is verified against these: the signing keys of the installations whose exports this one accepts."
    >
      {s.deployment.trusted_keys && (
        <p className="mb-2 text-sm text-slate-600">The deployment's trusted keys also apply{c.ui_config?.sources.trusted_keys === "both" ? ", with these" : ""}.</p>
      )}
      <ul className="space-y-2 text-sm">
        {s.trusted_keys.map((k) => (
          <li key={k.id} className="flex flex-wrap items-center gap-2">
            <b>{k.principal}</b> <code className="text-xs">{k.key_id}</code>
            <TrustedNote id={k.id} note={k.note} enabled={s.enabled} />
            {k.status === "pending" && <Pending kind="trusted_key" id={k.id} by={k.created_by} />}
            <span className="flex-1" />
            {s.enabled && (
              <ActionButton label="Remove" danger busy={remove.isPending && remove.variables === k.id} onClick={() => remove.mutate(k.id)}
                            confirm={`Stop trusting ${k.principal}'s exports?`} />
            )}
          </li>
        ))}
        {s.trusted_keys.length === 0 && <li className="text-xs text-slate-400">None registered here.</li>}
      </ul>
      {s.enabled && (
        <div className="mt-3 space-y-2 border-t border-slate-100 pt-3 text-sm">
          <textarea value={line} onChange={(e) => setLine(e.target.value)} rows={2}
                    placeholder={'The other installation\'s public line: argus-dev namespaces="git,argus-archive" ssh-ed25519 AAAA…'}
                    className="w-full rounded border border-slate-300 px-2 py-1 font-mono text-xs" />
          <div className="flex flex-wrap items-center gap-2">
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note, e.g. my laptop's ARGUS"
                   className="w-64 rounded border border-slate-300 px-2 py-1" />
            <ActionButton label="Trust it" busy={add.isPending} disabled={!line.trim()} onClick={() => add.mutate()}
                          confirm="Trust exports signed with this key?" />
            {add.isError && <ProblemWithStepUp error={add.error} />}
          </div>
        </div>
      )}
    </Section>
  );
}

function TrustedNote({ id, note, enabled }: { id: string; note: string | null; enabled: boolean }) {
  const refresh = useRefresh();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(note ?? "");
  const save = useMutation({ mutationFn: () => portabilityApi.noteTrustedKey(id, text), onSuccess: () => { refresh(); setEditing(false); } });
  if (!editing) {
    return (
      <span className="text-xs text-slate-500">
        {note ? `— ${note}` : ""}
        {enabled && <button type="button" className="ml-1 underline" onClick={() => setEditing(true)}>{note ? "edit" : "add a note"}</button>}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs">
      <input value={text} onChange={(e) => setText(e.target.value)} className="w-56 rounded border border-slate-300 px-2 py-0.5" />
      <button type="button" className="rounded bg-slate-900 px-2 py-0.5 text-white" onClick={() => save.mutate()} disabled={save.isPending}>Save</button>
      <button type="button" className="text-slate-500" onClick={() => setEditing(false)}>Cancel</button>
      {save.isError && <ProblemWithStepUp error={save.error} />}
    </span>
  );
}
