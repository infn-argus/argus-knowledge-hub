# Deploying the asset-management API

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
