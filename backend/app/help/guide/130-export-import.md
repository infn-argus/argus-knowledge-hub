---
title: Export and import (portability)
summary: Moving workspaces or a whole instance between ARGUS installations, step by step: by downloaded file or through a GitHub or GitLab repository, and from a local ARGUS to production.
keywords: [export, import, portability, backup, restore, clone, migrate, migration, move, copy, transfer, git, github, gitlab, repository, escrow, escrow-dev, artifact store, signing key, trusted keys, allowed_signers, deploy key, token, checkpoint, tar, download, upload, dry run, finalize, local to production]
order: 130
---

**Portability** moves data between ARGUS installations as a signed, verifiable archive: one workspace,
several, or the whole instance with its settings. Use it to move a local ARGUS's work to production, to
keep an off-site copy, or to give another installation a copy.

It is not the database backup: a backup restores *this* installation exactly as it was; an export is a
portable copy that another ARGUS verifies before it loads anything.

Exports and imports are for **administrators**: **Administration → Portability**.

## How it works, in one picture

**On the exporting ARGUS:** Export → Approve → Generate → then either **Publish to Git** or **Download
checkpoint (.tar)**.

**On the importing ARGUS:** Import from Git (the tag) or Upload (the `.tar`) → Verify → Dry run → Approve →
Execute → Finalize.

An export has three parts:

- the **checkpoint**: the signed manifest, saying exactly what is in the archive. It is what you
  download, or what is committed and tagged in Git;
- the **data**: the records, history and attached files, kept as content-addressed files in an
  **artifact store** (a directory on the exporting installation);
- the **signature**: made with the exporting installation's **signing key**. The importing installation
  checks it against its **trusted keys** (an `allowed_signers` file) and refuses anything unsigned,
  altered or signed by a key it does not trust.

So, to import elsewhere, the importing installation needs **all three**: the checkpoint (a file or a
Git tag), a copy of the artifact store **under the same store name**, and the exporter's public key
among its trusted keys.

## What an export carries, and what it does not

**Carried:** the types and their icons; people (as the identity profile allows); the workspaces, their
roles and who holds them; authority policies; assets with their relations, comments, history and
labels; tickets with their comments, history, links and watchers; documents with their revisions and
relations; attachments; ticket workflows; and the fact ledger with its full audit.

**Not carried**, to set up again on the other installation: **global values**, the **AI endpoint**
settings, saved **import configurations** (and their tokens), **API tokens**, **beam models**, and Ask
ARGUS conversations.

## Words you will see

| Word | Meaning |
|---|---|
| **Scope** | *Selected workspaces*, *Everything* (all workspaces, with the types, people and roles they use), *An increment* of an earlier published export, or *Evidence only* (a read-only copy) |
| **People in the archive** | how people are written: *Institutional reference* (ids only, the default), *Pseudonymized*, *Anonymous*, or *Full identity* (emails and names, needed to move people's accounts) |
| **Purpose** | backup, restore and migration keep full identities; analysis and external sharing are pseudonymized |
| **Restricted classes** | costs, personnel, security incidents…: included only if chosen, and only encrypted for an approved destination |
| **Repository** | a Git repository the archive is published to (*None* = generate only, then download) |
| **Artifact store** | where the data files go; required |
| **Import mode** | *clone*: records keep their ids, this installation keeps its own identity; *restore*: an empty installation takes the archive's identity; *merge*: alongside existing work; *selective*: choose workspaces in the dry run; *evidence*: read-only, nothing loaded |
| **Quarantine** | where an import's files wait until they are verified |
| **Staging** | a separate database where an import is loaded and checked before it touches the real one |

## Export, step by step

1. **Administration → Portability**, **Export**.
2. **Scope**: *Selected workspaces* (tick them) or *Everything (a full archive)*.
3. **Repository**: the Git repository to publish to, or *None (generate only)* to download a file.
4. **Artifact store for attachments**: the store configured here (for example `vault-dev` locally).
5. **Purpose** and **People in the archive**: to move your work to another installation of your own,
   choose *Migration* and *Full identity*, so people's accounts and authorship come along.
6. **Restricted classes to include**: leave empty unless you mean it.
7. Create it. The export page shows its steps:
   - **Approve**: under the default (*trusted*) policy you may approve your own export; under a stricter
     one, another administrator must.
   - **Generate**: ARGUS takes a consistent snapshot, writes and signs the archive, and checks it.
   - **Publish to Git** (with a repository): commits it and pushes a signed tag such as
     `export/full/2026-10-05@cp12-3f9a…`. Note the tag: the import asks for it.
   - **Download checkpoint (.tar)** (without a repository).

## Import, step by step

1. **Administration → Portability**, **Import**.
2. **Source**: *Git* (choose the **Repository** and give the **Signed export tag**; optionally the
   **Expected commit** you were told) or *Upload* (choose the `.tar` file).
3. **Mode**: *clone* for a copy that keeps its ids (the usual choice); *restore* only into an empty
   installation that should become the exporting one.
4. Create it. The import page shows its steps:
   - **Fetch into quarantine** (Git) — or the upload lands there.
   - **Verify**: signature, checksums, every data file in the artifact store. A failure says what is
     wrong and nothing is loaded.
   - **Dry run**: what would happen, row by row, per workspace. In *selective* mode, choose the
     workspaces here, and their ids here if they should differ. Run it again after any change.
   - **Approve**: as shown by the dry run. Under a stricter policy, or for *merge* and *restore*,
     another administrator approves.
   - **Execute**: loads it into the **staging** database and checks it there. Nothing in the real
     database changes. If it is interrupted, **Resume in staging**.
   - **Finalize**: moves it into the real database in one step, and commits only if the result equals
     what staging showed. If anything differs, nothing is committed and you can retry.
5. Changed your mind before *Finalize*? **Discard**: nothing it loaded remains.

After an import, finished files (quarantine, staging, evidence copies) are removed by the daily cleanup
(after one day in production).

## Using a GitHub or GitLab repository

A Git repository is the convenient way to move archives repeatedly, or to keep them off-site. Each
installation needs it **configured once** (an administrator of the installation does this; the values
go in the API's environment, in production `api.env` in the chart's `values-production.yaml`, and the
keys in the `argus-portability` Secret):

1. **Create an empty, private repository**: on GitHub *New repository* (private, no README); on GitLab
   (for example `baltig.infn.it`) *New project → Create blank project*, private.
2. **Choose how ARGUS authenticates**:
   - **SSH deploy key** (recommended):
     ```
     ssh-keygen -t ed25519 -N '' -C argus-escrow-deploy -f deploy-key-escrow
     ```
     Add `deploy-key-escrow.pub` to the repository: GitHub *Settings → Deploy keys → Add deploy key*,
     tick **Allow write access** on the installation that exports; GitLab *Settings → Repository →
     Deploy keys*, with **Grant write permissions**. An installation that only imports needs read only.
     Pin the server's host key: `ssh-keyscan github.com > known_hosts` (or your GitLab host), and check
     the fingerprints against the ones the provider publishes.
   - **HTTPS token**: a GitHub fine-grained token with *Contents: read and write* on that repository, or
     a GitLab project access token with *write_repository*. Save it in a file. Put a user name in the
     address so Git asks only for the password, which ARGUS answers with the token:
     `https://x-access-token@github.com/<org>/<repo>.git` (GitHub) or
     `https://oauth2@<gitlab host>/<group>/<repo>.git` (GitLab).
3. **Tell ARGUS about it**, naming the repository (here `escrow`):
   ```
   ARGUS_PORTABILITY_REPOSITORIES=escrow=ssh://git@github.com/<org>/<repo>.git
   ARGUS_PORTABILITY_REPOSITORY_KEYS=escrow=/etc/argus/portability/deploy-key-escrow
   ARGUS_PORTABILITY_SSH_KNOWN_HOSTS=/etc/argus/portability/known_hosts
   ```
   or, with a token:
   ```
   ARGUS_PORTABILITY_REPOSITORIES=escrow=https://x-access-token@github.com/<org>/<repo>.git
   ARGUS_PORTABILITY_REPOSITORY_TOKENS=escrow=/etc/argus/portability/token-escrow
   ```
4. **Signing and trust**: each installation that exports has a signing key
   (`ARGUS_PORTABILITY_SIGNING_KEY`, an Ed25519 key, and `ARGUS_PORTABILITY_SIGNER`); each that imports
   lists the exporters it trusts in `ARGUS_PORTABILITY_TRUSTED_KEYS` (an `allowed_signers` file, one
   line per exporter's public key).
5. Restart the API (in production, Argo CD does it when the values change). **Administration →
   Portability** then lists the repository under *Repositories*, and the export form offers it.

The archive's data still travels through the **artifact store**: give the importing installation a
store with the same name and a copy of its files (or a shared location), as below.

## From your local ARGUS to production

The usual first load of a new production installation, with the local one's workspaces and settings.

**On the local installation** (`docker compose`):

1. **Administration → Portability → Export**: *Everything (a full archive)*, purpose *Migration*,
   people *Full identity*, repository `escrow-dev` (or *None* to download), artifact store `vault-dev`.
   Approve, Generate, then Publish to Git (note the tag) or Download the checkpoint.
2. The files to carry across, from the API container's `/data/portability/dev/`:
   - `escrow.git` (the repository, if you published) or the downloaded `.tar`;
   - `artifacts/` (the `vault-dev` store with the data);
   - `allowed_signers` (the local signing key's public line, which production must trust).

**On production** (an administrator of the cluster):

3. Copy `escrow.git` and `artifacts/` into the API's portability volume, for example:
   ```
   kubectl -n argus cp escrow.git <api pod>:/data/portability/escrow-local.git
   kubectl -n argus cp artifacts <api pod>:/data/portability/vault-dev
   ```
4. Trust the local key: put `allowed_signers` in the `argus-portability` Secret, and set in
   `values-production.yaml` under `api.env`:
   ```
   ARGUS_PORTABILITY_TRUSTED_KEYS: /etc/argus/portability/allowed_signers
   ARGUS_PORTABILITY_ARTIFACT_STORES: vault-dev=/data/portability/vault-dev
   ARGUS_PORTABILITY_REPOSITORIES: escrow-local=/data/portability/escrow-local.git
   ```
   Push it; Argo CD restarts the API with it.
5. **Administration → Portability → Import**: source *Git*, repository `escrow-local`, the tag from step
   1 (or source *Upload* with the `.tar`), mode **clone**. Then Fetch, Verify, Dry run, Approve, Execute,
   Finalize.

Then set up on production what an export does not carry: the AI endpoint (*AI endpoint*), import
configurations (*Imports*), global values and beam models (upload the model files again). The local
installation's test users come along with *Everything*; remove or deactivate the ones you do not want
afterwards (*Administration → Users*).

## When something goes wrong

| What you see | What it means, and what to do |
|---|---|
| *no signing key is configured* | this installation cannot export yet: set `ARGUS_PORTABILITY_SIGNING_KEY` |
| *an artifact store is needed* | choose an artifact store in the export form, or configure one |
| *artifact store 'vault-dev' is not configured here* | the importing installation needs a store with that same name, holding a copy of the exporter's files |
| Verify fails on the signature | the exporter's public key is not in this installation's trusted keys, or the archive was changed |
| *another administrator must approve* | the policy wants two people: ask a second administrator |
| Execute stopped half way | **Resume in staging**; nothing reached the real database |
| Finalize reports a difference | nothing was committed; read the reconciliation, then retry or Discard |
| Not enough space | an import needs room for the files in quarantine and the staging database; ask for disk space first |
