# Proposal: object-detection-in-page-images

## Summary

Give anonymiq a locally run detector that finds signatures, faces and number plates as objects in page images and answers their regions to OpenRegister's image seam, which burns them like any other region.

- Rows: 4.20 "A signature, a face or a number plate is found as an object in a page image and masked" (not statutory).
- Wave: 2.
- Depends on: `openregister/anonymisation-image-seam` (https://github.com/ConductionNL/openregister/issues/4380), the caller and the contract.
- Decision: D6 (2026-10-05), anonymiq gets an `openspec/` and owns the detector while OpenRegister owns the seam; and the detector half of D5, which kept filinq's `image-redaction` to signatures until a detector exists.

Build rules: openspec/woo-build-rules.md (in this Python repo: ruff, mypy and pytest, as its note says)

## Where this lives

anonymiq had no `openspec/` folder; this change creates it. anonymiq is a
standalone Python FastAPI service, deployed as a container (Helm in
`charts/`, Argo CD in `argocd/`), with no `appinfo/info.xml`. It is not a
Nextcloud app and not an AppAPI ExApp. So the folder follows the fleet's shape
(`openspec/config.yaml`, `openspec/specs/`, `openspec/changes/<name>/` with
`proposal.md`, `specs/<capability>/spec.md` and `tasks.md`), with the
fleet's `spec-driven` schema, and the tasks use the repo's own Python tooling
(uv, pytest, ruff, mypy) instead of composer and npm.

## Why

Woo capability row 4.20, "A signature, a face or a number plate is found as an
object in a page image and masked". Our column reads `no`: "detection is over
extracted text only (lib/Service/TextExtraction/EntityRecognitionHandler.php)
and replacement is text replacement (PdfTextReplacer). ocrEnabled in
lib/Service/Settings/FileSettingsHandler.php finds text in a scan; nothing
finds a signature, a face or a number plate as an object in the pixels". The
gap register names the missing half: "Detect signatures, faces and number
plates as objects in page images on the OR image seam and burn them like any
other region." Build plan: new spec, wave 2, size L.

Ruben's decision **D6** of 2026-10-05: give anonymiq an `openspec/` and make it
own the detector; OpenRegister owns the seam
(`openregister/anonymisation-image-seam`). Decision **D5** kept filinq's
`image-redaction` to signatures until a detector exists; this change is that
detector. anonymiq was last changed on 2026-08-23 (`eb4e7b0`, the rename from
OpenAnonymiser), and `development` equals that commit.

## What changes

1. A new route, `POST /api/v1/image/regions`, that takes one page image and
   returns the objects found in it as regions, in exactly the shape
   OpenRegister's seam expects.
2. Three classes: `SIGNATURE`, `FACE` and `LICENSE_PLATE`. Each is backed by a
   locally run model. A class is only offered when its model is loaded and has
   met the recall floor on the evaluation corpus; the answer lists which
   classes were looked for, so an absent class is never read as "none found".
3. `GET /api/v1/image/regions/about`: the detector's name, version, classes,
   the models with their versions and licences, and the precision and recall
   per class on the named evaluation corpus, which OpenRegister's
   `anonymisation-discloses-itself` (REQ-ADI-001, REQ-ADI-002) reports.
4. A labelled evaluation corpus of synthetic page images (no real personal
   data) in `tests/fixtures/image-regions/`, and a test that measures recall
   and precision per class on it and fails below the floor.

## The contract with OpenRegister

From `openregister/anonymisation-image-seam` (REQ-AIS-002 and its task 2.2,
`tests/Contract/AnonymiqImageRegionsContractTest.php` on that side):

- Request: `POST /api/v1/image/regions` with JSON `{image, page}`: `image` the
  page image as base64 (PNG, JPEG, TIFF or WebP), `page` an integer or null for
  a standalone image.
- Response 200: `{regions: [{page, box: {x, y, w, h}, entityType, confidence}],
  detector: {name, version}}`, `box` values between 0 and 1 relative to the
  image, `confidence` between 0 and 1. This change adds `detector.classes`
  (the classes that were looked for). The extra key is additive; the
  OpenRegister contract test pins only the keys it reads and must keep
  passing.
- An image that cannot be decoded answers 422 with a reason, never 200 with no
  regions.

## Fail closed

- A class whose model did not load, or did not meet the recall floor, is not
  in `detector.classes`. OpenRegister records that class as not run.
- An undecodable or oversized image (over 40 megapixels, or a body over 25 MB)
  answers 422 or 413, never an empty 200.
- The image is processed in memory and never written to disk, the database or
  a log. A log line carries the request id, the image size and the region
  count, never pixels or base64.
- A timeout inside a model answers 503, so OpenRegister records `failed`, not
  clean.

## Licences and models

anonymiq is EUPL-1.2. Every model and its weights must carry a licence that
allows bundling with EUPL-1.2 software and use by a government organisation:
no AGPL weights (this rules out Ultralytics YOLO weights), no model that calls
out to a remote service, no weights fetched at request time. The building
agent records each model's source, version, licence and sha256 in
`docs/image-regions.md` and in the `about` answer, and pins the weights in the
image build.

## App absent

- OpenRegister absent, or not configured to call anonymiq: the route is
  simply not called. Nothing else in anonymiq changes.
- anonymiq absent: OpenRegister's seam records `objectDetection: not-run` with
  `not-installed` (its REQ-AIS-002), so nobody reads a clean result as "no
  faces".

## Inherited, not fixed here

The existing routes have no authentication and CORS allows every origin
(`src/api/main.py`). This change does not widen that: the new route requires
a bearer key when `ANONYMIQ_API_KEY` is set, and logs a startup warning when
it is not. Hardening the existing routes is its own change.

## Dependencies and wave

- `openregister/anonymisation-image-seam` (wave 1): the caller and the
  contract.
- Wave 2. Implements decision D6, and the detector half of D5.

## Done

Merged on `development` with CI green, the image built and deployed to
staging, and one call from OpenRegister's seam recorded in the PR body. Row
4.20 is `production` once anonymiq's release is deployed where the store
releases of OpenRegister call it.
