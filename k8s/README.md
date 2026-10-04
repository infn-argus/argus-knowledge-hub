# Deploying the asset-management API

## Releases: a tag is a deployment

Once set up (below), releasing is:

```
git tag v1.33.0 && git push origin v1.33.0
```

`.github/workflows/release.yml` then:

1. runs the backend tests inside the backend image, against Postgres with pgvector, and type-checks
   and builds the web app; a failure stops the release here, before anything is pushed;
2. builds both images and pushes them to ghcr.io as `1.33.0` and `latest`;
3. commits `Deploy 1.33.0` to `main`, setting the two `newTag`s in `k8s/kustomization.yaml`.

Argo CD watches `k8s/` on `main` (`k8s/argocd/application.yaml`) and rolls that version out. So
`main` always says which version runs, and going back is reverting the `Deploy` commit (or setting
`newTag` by hand). The API applies its database migrations on start.

What Argo CD manages is what `k8s/kustomization.yaml` lists: the namespace, the API and web app with
their services and ingresses, and the attachments volume. The Postgres manifests are left out,
because the cluster may run a pgvector build the manifest does not name. The portability CronJobs are
left out until their Secret exists. Both are still applied by hand. Argo CD never deletes
(`prune: false`); it puts back hand edits to what it manages (`selfHeal`).

### Setting it up, once

With `KC="kubectl --kubeconfig ~/kubeconfigs/cloud-config.txt"`:

1. **The packages accept the workflow.** On GitHub, for each of `argus-knowledge-hub-backend` and
   `argus-knowledge-hub-web`: *Package settings → Manage Actions access → Add repository*
   `infn-argus/argus-knowledge-hub`, role **Write**. Without it the push is refused (403).
2. **The workflow may push to `main`.** If `main` is protected, allow `github-actions[bot]` to bypass
   the rule for the `Deploy` commit, or the last step fails (the images are pushed regardless).
3. **Argo CD is installed** in the cluster (`kubectl get crd applications.argoproj.io`). If it is not:
   ```
   $KC create namespace argocd
   $KC apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
   ```
4. **Check what it would change**, then hand the namespace over:
   ```
   $KC diff -k k8s/        # the live objects against the manifests; set newTag to what runs first
   $KC apply -f k8s/argocd/application.yaml
   ```
   The repository is public, so Argo CD needs no credentials to read it.

## Building and rolling out by hand

Target: the INFN cluster via `kubectl --kubeconfig ~/kubeconfigs/cloud-config.txt`.

## 1. Build and push the image

```
cd ../backend
./deploy.sh 0.1.0
```

Requires `docker login ghcr.io -u <your-github-username>` first, with a GitHub
PAT that has `write:packages` scope. The `ghcr.io/infn-argus/argus-knowledge-hub-backend`
package should be public (Package settings → Change visibility) so the cluster
needs no `imagePullSecret`. If you'd rather keep it private, create one:

```
kubectl --kubeconfig ~/kubeconfigs/cloud-config.txt create secret docker-registry ghcr-pull-secret \
  --namespace assetmanagement \
  --docker-server=ghcr.io \
  --docker-username=<github-username> \
  --docker-password=<github-PAT-with-read:packages> \
  --docker-email=<your-email>
```

...and add `imagePullSecrets: [{name: ghcr-pull-secret}]` under `spec.template.spec`
in `api-deployment.yaml`.

## 2. Create the namespace and secrets

```
KC="kubectl --kubeconfig ~/kubeconfigs/cloud-config.txt"

$KC apply -f namespace.yaml

$KC create secret generic postgres-secret -n assetmanagement \
  --from-literal=username=assetmanagement \
  --from-literal=password="$(openssl rand -base64 24)"

$KC create secret generic api-secret -n assetmanagement \
  --from-literal=database-url="postgresql://assetmanagement:<same password as above>@postgres:5432/assetmanagement" \
  --from-literal=token-pepper="$(openssl rand -base64 32)"
```

Never commit the real values — these two secrets are the only place credentials live.

## 3. Deploy everything else

```
$KC apply -f postgres-pvc.yaml -f postgres-deployment.yaml -f postgres-service.yaml
$KC apply -f attachments-pvc.yaml -f api-deployment.yaml -f api-service.yaml -f api-ingress.yaml
```

## 4. Verify

```
$KC -n assetmanagement get pods
curl https://assets-api.90.147.174.30.myip.cloud.infn.it/health
```

## 5. Mint the first API token

```
$KC -n assetmanagement exec deploy/assetmanagement-api -- \
  python scripts/create_token.py ws-default "Default Workspace" cli
```

Save the printed token — it's the `Authorization: Bearer <token>` value for every
request after this, and it is not recoverable once you lose it (mint a new one
with the same command if that happens).

## Postgres with pgvector (Ask ARGUS's written-knowledge search)

The API runs without it, but Ask ARGUS can then only use exact lookups. To enable the search over
documents, tickets and attached files, run the same Postgres 16 with the pgvector extension. Use the
build with the **same Debian release** as the current one, or Postgres reports a collation version
mismatch (text indexes built under one C library may sort differently under another):

```
$KC -n assetmanagement exec deploy/postgres -- psql -U assetmanagement -d assetmanagement -tAc "select version()"
```

`pgdg13` in the answer is Debian 13: use `pgvector/pgvector:pg16-trixie`; `pgdg12` is Debian 12: use
`pgvector/pgvector:pg16-bookworm`. Back up first, then:

```
$KC -n assetmanagement exec deploy/postgres -- pg_dump -U assetmanagement -Fc assetmanagement > argus-before-pgvector.dump
$KC -n assetmanagement set image deployment/postgres postgres=pgvector/pgvector:pg16-trixie
$KC -n assetmanagement rollout status deployment/postgres
```

The data volume is reused as it is. Then restart the API (its startup migration creates the extension and
the index tables) and build the index from *Workspace → AI*, or:

```
$KC -n assetmanagement rollout restart deployment/assetmanagement-api
$KC -n assetmanagement exec deploy/assetmanagement-api -- python -m app.services.knowledge_index all
```

The chat streams its answers as server-sent events: an ingress that buffers responses would hold them
back until the end. The API sends `X-Accel-Buffering: no`, which nginx ingress honours.

## Redeploying a new API image version

```
cd ../backend && ./deploy.sh <new-version>
kubectl --kubeconfig ~/kubeconfigs/cloud-config.txt -n assetmanagement \
  set image deployment/assetmanagement-api api=ghcr.io/infn-argus/argus-knowledge-hub-backend:<new-version>
```

The container's startup command runs `alembic upgrade head` before serving,
so schema migrations apply automatically on rollout.

## Web app

A React/Vite SPA (`webapp/`) served by nginx, deployed the same way:

```
cd ../webapp
./deploy.sh 0.1.0
```

Same registry-visibility note as the API image applies — make
`ghcr.io/infn-argus/argus-knowledge-hub-web` public, or wire up an
`imagePullSecret` in `web-deployment.yaml`.

```
$KC apply -f web-deployment.yaml -f web-service.yaml -f web-ingress.yaml
```

It's stateless (no Secrets, no PVC) — the API server URL and Bearer token are
entered once in the browser on first load and kept in that browser's
`localStorage`, not baked into the image. Live at
`https://assets.90.147.174.30.myip.cloud.infn.it`.

Redeploy the same way as the API:

```
cd ../webapp && ./deploy.sh <new-version>
kubectl --kubeconfig ~/kubeconfigs/cloud-config.txt -n assetmanagement \
  set image deployment/assetmanagement-web web=ghcr.io/infn-argus/argus-knowledge-hub-web:<new-version>
```

## Portable exports and imports

Settings are in `portability-configmap.yaml`, secrets in two Secrets (`portability-secret.example.yaml`
shows their keys; it is a template, never applied), volumes in `portability-pvc.yaml`, scheduled work
in `portability-cronjobs.yaml`. Background: `docs/operations.md`, "Portable exports", and
`docs/export-import-design.md` §20.

### 1. Keys and credentials (on an administrator's machine, not the cluster)

```
ssh-keygen -t ed25519 -N '' -C argus-portability -f signing_key
echo "argus-portability namespaces=\"git,argus-archive\" $(cat signing_key.pub)" > allowed_signers
ssh-keygen -t ed25519 -N '' -C argus-escrow-deploy -f deploy-key-escrow
ssh-keyscan git.example.org > known_hosts        # check the fingerprint against the Git server's
openssl rand -base64 32 > pseudonym-salt
```

Register `deploy-key-escrow.pub` on the `escrow` repository as a deploy key: write access here
(an exporting instance), read-only on instances that only import. On the Git server, protect `main`
and the `export/*` tags against deletion and force-push.

### 2. The Secrets

```
$KC create secret generic argus-portability -n assetmanagement \
  --from-file=signing_key --from-file=allowed_signers \
  --from-file=deploy-key-escrow --from-file=known_hosts \
  --from-literal=pseudonym-salt="$(cat pseudonym-salt)"
```

Then remove the local copies of `signing_key`, `deploy-key-escrow` and `pseudonym-salt` (keep the
private keys in the institutional secret store only). Add `--from-file=recipients-<repository>` for
a restricted destination.

**Decrypting an encrypted archive** is the only time a recipient private key enters the cluster:

```
$KC create secret generic argus-portability-decryption -n assetmanagement --from-file=escrow-officer
# … wait a minute for the files to appear, then verify, dry run, approve, execute, finalize …
$KC delete secret argus-portability-decryption -n assetmanagement
```

### 3. The importer role (staging databases)

A dedicated role creates and drops the per-import staging databases, not the application's role:

```
$KC -n assetmanagement exec deploy/postgres -- psql -U assetmanagement -d assetmanagement -c \
  "CREATE ROLE argus_importer LOGIN CREATEDB PASSWORD '<generated>'"
$KC -n assetmanagement get secret api-secret -o json \
  | jq --arg v "$(printf %s 'postgresql://argus_importer:<generated>@postgres:5432/assetmanagement' | base64)" \
       '.data["portability-staging-url"]=$v' | $KC apply -f -
```

Exclude `argus_stage_*` and `argus_drill_*` databases from backups.

### 4. Apply

```
$KC apply -f portability-pvc.yaml -f portability-configmap.yaml
$KC apply -f api-deployment.yaml -f portability-cronjobs.yaml
$KC -n assetmanagement exec deploy/assetmanagement-api -- python -m app.portability policy
```

* **`portability-artifacts` must be backed up**; it holds the archive data that is not in Git.
* **The drill CronJob is created suspended.** Resume it after the first full export is published:
  `$KC -n assetmanagement patch cronjob portability-restore-drill -p '{"spec":{"suspend":false}}'`.
  It runs on 1 January and 1 July. Sign off each result with
  `python -m app.portability drill-signoff <drill_id> --by <admin>`.
* **Both portability volumes are ReadWriteOnce.** The CronJobs therefore run on the API pod's node
  (pod affinity).
* **The API's 512Mi memory limit has not been sized for exports.** Run
  `python -m app.portability cycle …` on a non-production copy first, and set the limit from the peak
  memory it records.

### Annual rotation

1. Generate a new signing key and add its allowed-signers line on every importing instance.
2. Replace `signing_key` (and `allowed_signers`) in the Secret.
3. Restart the API: `$KC -n assetmanagement rollout restart deploy/assetmanagement-api`.
4. Run one export and a manual drill:
   `$KC -n assetmanagement create job --from=cronjob/portability-restore-drill drill-rotation`.
5. Rotate the deploy key the same way, and revoke the old one on the Git server.
