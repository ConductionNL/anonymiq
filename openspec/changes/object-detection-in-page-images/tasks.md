# Tasks: object-detection-in-page-images

Woo row 4.20. Wave 2, after `openregister/anonymisation-image-seam`. Decisions
D6 and D5. Every test named here fails on `development` today: there is no
`/api/v1/image/regions` route.

## 1. Models and licences

- [ ] 1.1 Choose one locally run model per class (SIGNATURE, FACE, LICENSE_PLATE), run through ONNX Runtime or an equivalent permissively licensed runtime. Each model's licence must allow bundling with EUPL-1.2 and government use; no AGPL weights, no remote calls, no download at request time. Record source, version, licence and sha256 per model in `docs/image-regions.md`. If no model with a fitting licence reaches the recall floor for a class, ship without that class and say so in the PR body; do not lower the floor to make it pass.
  - Test: pytest `tests/test_image_regions_models.py::test_every_model_has_a_recorded_licence_and_hash` (reads the manifest and compares the sha256 of the pinned weights).
- [ ] 1.2 Pin the weights in the image build (`Dockerfile`), with the sha256 checked at build time. Add the runtime to `pyproject.toml` and `uv.lock`.
  - Test: the Docker build fails on a changed hash (a CI step, recorded in the PR body).

## 2. The evaluation corpus

- [ ] 2.1 Build `tests/fixtures/image-regions/`: synthetic page images (generated letters with drawn signatures, generated or licence-cleared faces, rendered number plates on synthetic cars), a labels file with boxes per image, and a README naming the corpus version and how each image was made. No real personal data.
  - Test: pytest `tests/test_image_regions_corpus.py::test_every_image_has_labels_and_no_label_points_outside_its_image`.
- [ ] 2.2 The evaluation: precision and recall per class at the default confidence, intersection over union 0.5, written to `src/api/image_regions/evaluation.json`.
  - Test: pytest `tests/test_image_regions_evaluation.py::test_every_offered_class_meets_the_recall_floor`.

## 3. The route

- [ ] 3.1 `src/api/routers/image_regions.py` (router included in `src/api/routers/__init__.py`), `src/api/image_regions/detector.py` (load models at start, classes that loaded and met the floor), DTOs in `src/api/dtos.py`. Size and decode checks before any model runs.
  - Test: pytest `tests/test_image_regions.py::test_a_signature_on_page_two_is_found`, `::test_an_undecodable_image_is_422`, `::test_an_oversized_image_is_413`, `::test_a_model_timeout_is_503`, `::test_a_missing_model_drops_its_class`. Show `test_a_signature_on_page_two_is_found` failing on `development` first (404); paste the line in the PR body.
  - Wiring: the tests call the route through FastAPI's `TestClient` on `src.api.main.app`, so the router is proven reachable from the app, not only importable.
- [ ] 3.2 The contract with OpenRegister: copy the recorded request and response that `openregister/anonymisation-image-seam`'s `AnonymiqImageRegionsContractTest` pins into `tests/fixtures/image-regions/openregister-contract.json`, and test the answer against it. If that OpenRegister test has not merged, stop and say so in the PR body; do not invent the shape.
  - Test: pytest `tests/test_image_regions_contract.py::test_the_answer_matches_openregisters_contract`.
- [ ] 3.3 `GET /api/v1/image/regions/about`.
  - Test: pytest `tests/test_image_regions.py::test_about_lists_models_and_evaluation`.

## 4. Privacy and access

- [ ] 4.1 In-memory processing, the log line, the optional bearer key and the startup warning.
  - Test: pytest `tests/test_image_regions.py::test_the_image_is_not_logged_or_stored`, `::test_a_configured_key_is_required`, `::test_no_key_configured_logs_one_warning`.

## 5. Deployment and docs

- [ ] 5.1 `charts/` values for the new settings (`ANONYMIQ_API_KEY` from a secret, `IMAGE_REGIONS_RECALL_FLOOR`, `IMAGE_REGIONS_MIN_CONFIDENCE`), memory and CPU requests sized for the models; `DEPLOYMENT.md` and `docs/api-examples.md` with a curl example.
  - Test: `validate-argocd.yml` and a Helm template render, exit codes recorded in the PR body.
- [ ] 5.2 One live call from OpenRegister's seam on the dev environment to a staging deployment, request id and region count recorded in the PR body.

## Verification

- [ ] Own clone, `git checkout --no-track -b <branch> origin/development`, `TMPDIR` a sibling outside the clone.
- [ ] Once before push: `uv sync`, `uv run ruff check`, `uv run mypy src`, `uv run pytest`. Read the pytest summary line, not only the exit code.
- [ ] CI is not evidence on its own here: `.github/workflows/feature-testing.yml` runs `python run_tests.py` from the repo root, and on `development` that script lives at `scripts/run_tests.py`. Record the local pytest summary in the PR body, and say whether the CI test step actually ran. Fixing the workflow is inherited debt, one sentence in the PR body.
- [ ] `openspec validate object-detection-in-page-images --type change --strict` passes.
- [ ] One PR, `--base development`; merge `development` in, never rebase; no `Co-Authored-By` trailer. Never `pkill -f` a process by name.
- [ ] Done means merged on `development` with CI green and deployed to staging. Row 4.20 is `production` once a release is deployed where OpenRegister's store release calls it.
