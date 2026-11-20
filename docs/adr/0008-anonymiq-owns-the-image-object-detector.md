# 8. anonymiq owns the image object detector; OpenRegister owns the seam

- Status: Accepted (2026-10-05, decision D6); not built yet

## Context

Finding a signature, a face or a number plate as an object in a page image needs a vision model. OpenRegister has a text pipeline only. anonymiq is the natural home for models, but had no OpenSpec.

## Decision

anonymiq gets an `openspec/` folder and owns the detector; OpenRegister owns the seam that calls it (`openregister/anonymisation-image-seam`). This also settles the detector half of decision D5, which kept filinq's `image-redaction` to signatures until a detector exists.

## Consequences

- The change `openspec/changes/object-detection-in-page-images/` specifies the detector: a route `POST /api/v1/image/regions` in the region shape OpenRegister's seam expects, an `about` route, and three classes (`SIGNATURE`, `FACE`, `LICENSE_PLATE`), each offered only when its locally run model is loaded and meets a recall floor.
- Models must carry a licence that allows bundling with EUPL-1.2 and government use: no AGPL weights, no remote calls and no weights fetched at request time.
- When anonymiq is absent, OpenRegister records object detection as not run, so nobody reads a clean result as "no faces".

## Source

`openspec/woo-decisions.md`, section "D6. Gaps no app can own yet"; `openspec/changes/object-detection-in-page-images/proposal.md`.
