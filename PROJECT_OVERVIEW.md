# Anonymiq – Project Overview (for new engineers)

## Doel & kern
Anonymiq is een API voor detectie en anonimisering van PII in Nederlandse tekst en PDF’s. De service combineert NER‑modellen met regelgebaseerde herkenners (patterns) en biedt string‑ en document‑endpoints.

## Architectuur (kort)
- Endpoints (prefix `/api/v1`): `GET /health`, `POST /analyze`, `POST /anonymize`, documenten: `POST /documents/upload`, `GET /documents/{id}/metadata`, `POST /documents/{id}/anonymize`, `GET /documents/{id}/download`.
- Kernbestanden: `src/api/main.py`, routers (`src/api/routers/*`), services (`src/api/services/text_analyzer.py`), utils (`src/api/utils/*`), DTO’s (`src/api/dtos.py`), DI/DB (`src/api/dependencies.py`, `src/api/database.py`).
- Helm chart: `charts/openanonymiser/**` (deployment/ingress/values).

## NLP & entiteiten
- Patterns (Presidio): `IBAN`, `PHONE_NUMBER`, `EMAIL`.
- NLP (NER – SpaCy of Transformers): `PERSON`, `LOCATION`, `ORGANIZATION`, `ADDRESS` (best‑effort).
- Default engine: SpaCy (`nl_core_news_md`). Override per request met `nlp_engine: "transformers"` (model: `pdelobelle/robbert-v2-dutch-base`).

## Run & Test
- Lokaal (dev):
  - `uv venv && uv sync && uv run api.py`
- Docker Compose:
  - `docker-compose up -d` (API op http://localhost:8001/api/v1/docs)
- Use‑case tests (staging):
  - `ANONYMIQ_BASE_URL="https://api.openanonymiser.accept.commonground.nu" pytest -q tests/test_usecases.py`

## Environments & images
- Staging (accept): image tag `dev`, pullPolicy `Always`, host `api.openanonymiser.accept.commonground.nu`.
- Productie: image tag `main` (of `latest`), host `api.openanonymiser.commonground.nu`.
- ArgoCD apps: `argocd/staging-app.yaml` (branch `staging`, `values-staging.yaml`), `argocd/production-app.yaml` (branch `main`, default `values.yaml`).

## Ingress/TLS
- Staging: TLS secret `openanonymiser-accept-tls`, issuer `letsencrypt-prod`, ingress.class `nginx`.
- Prod: TLS secret `openanonymiser-tls`, issuer `letsencrypt-prod`.
- Verifiëren: `kubectl get certificate,challenge,order -n <ns>` en `curl -I https://…/api/v1/health`.

## CI/CD
- `.github/workflows/docker-build.yml`: bouwt/pusht images
  - `main` → `:main` en `:latest`
  - `staging/development` → `:dev`
- `.github/workflows/validate-argocd.yml`: checkt branch/values/ingress/imagetag per environment.
- ArgoCD synct staging/prod automatisch met hun branch/values.

## Known pitfalls
- SpaCy model ontbreekt (E050) → image met `nl_core_news_md` bouwen; staging moet `:dev` gebruiken.
- Ingress host collision (accept vs prod) → staging moet accept‑host gebruiken (`values-staging.yaml`).
- Cert‑issues (self‑signed/none) → issuer/ingress.class controleren en Certificate resources checken.

## Next steps
- Draai lokaal: `uv run api.py` en test met `tests/test_usecases.py`.
- Check staging met `:dev` image en voer curls/pytest uit.
- Lees `docs/use-cases.md`, `docs/api-examples.md`, `charts/openanonymiser/values*.yaml`.

## Verifieer met commando’s (niet uitvoeren)
- Health: `curl -s https://api.openanonymiser.accept.commonground.nu/api/v1/health`
- Analyze (voorbeeld): `curl -s -X POST https://…/analyze -H "Content-Type: application/json" -d '{"text":"Piet in Utrecht","language":"nl"}'`
- Anonymize (voorbeeld): `curl -s -X POST https://…/anonymize -H "Content-Type: application/json" -d '{"text":"IBAN NL91ABNA0417164300"}'`
- K8s/Argo: `kubectl -n openanonymiser-accept get ingress openanonymiser -oyaml`
  `kubectl -n openanonymiser-accept get certificate,challenge,order`
  `kubectl -n argocd get application openanonymiser-accept -oyaml`

