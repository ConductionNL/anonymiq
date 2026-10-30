# Anonymiq deployment guide

## Overview

Images live at `ghcr.io/conductionnl/anonymiq`. Argo CD deploys the Helm chart in `charts/openanonymiser`: staging follows the `staging` branch and runs the `dev` image, production follows `main` and runs the `main` image.

```
feature branch -> pull request into development -> staging -> main -> version tag -> production
```

A merge to `main` publishes nothing. Production gets a new image only when a version tag `vX.Y.Z` is pushed.

## Workflows

| Workflow | Trigger | What it does |
| --- | --- | --- |
| `ci.yml` | Every pull request, every push except to `main`, and called by the deploy workflows | ruff, mypy, pytest with coverage, pip-audit (report only), CycloneDX SBOM, Helm lint, UI lint and build |
| `docker-build.yml` | Pull requests into `main` and `development`; pushes to `staging` and `development` | Builds the image and scans it with Trivy; on a push it also publishes `:dev` |
| `deploy-staging.yml` | Push to `staging` | Runs CI, then publishes `:dev` and `:staging-<date>-<sha>`, then checks the staging health route |
| `deploy-production.yml` | Push of a tag `vX.Y.Z` | Runs CI, builds, scans with Trivy, publishes `:vX.Y.Z`, `:latest` and `:main`, creates the GitHub release, then checks the production health route |
| `retag-image.yml` | Manual | Copies an image pinned by digest to version, `main`, `latest` or `dev` tags without rebuilding |
| `validate-argocd.yml` | Pull requests into `main`, `staging` and `development`; pushes to `main` and `staging` | Checks the Argo CD applications and the Helm values |

Publishing a feature image from a feature branch is opt in: set the repository variable `PUBLISH_FEATURE_IMAGES=true`.

## Releasing to production

```bash
git checkout main
git pull
git tag v1.2.3
git push origin v1.2.3
```

## Image tags

```bash
ghcr.io/conductionnl/anonymiq:dev                       # staging
ghcr.io/conductionnl/anonymiq:staging-20251029-abc1234  # one staging build
ghcr.io/conductionnl/anonymiq:v1.2.3                    # a release
ghcr.io/conductionnl/anonymiq:main                      # production
ghcr.io/conductionnl/anonymiq:latest                    # the latest release
```

## 🧪 Testing Commands

### Local Testing
```bash
uv run api.py &
python tests/integration/test_endpoints.py
./scripts/test_endpoints.sh
```

### Cloud Testing
```bash
python tests/integration/test_endpoints.py https://api.openanonymiser.commonground.nu
./scripts/test_endpoints.sh https://api.openanonymiser.commonground.nu
```

### Docker Testing
```bash
docker run -d -p 8081:8080 ghcr.io/conductionnl/anonymiq:dev
python tests/integration/test_endpoints.py http://localhost:8081
```

## 🔧 Manual Cluster Operations

### Deploy Latest Dev Image
```bash
kubectl set image deployment/openanonymiser \
  openanonymiser=ghcr.io/conductionnl/anonymiq:dev \
  -n openanonymiser
```

### Check Deployment Status
```bash
kubectl get pods -n openanonymiser
kubectl describe deployment openanonymiser -n openanonymiser
kubectl logs -l app=openanonymiser -n openanonymiser --tail=50
```

### Force ArgoCD Sync
```bash
argocd app sync openanonymiser
# Or via ArgoCD UI
```
