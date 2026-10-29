# Spec: image object detection

## ADDED Requirements

### Requirement: A page image is answered with the objects found in it, in OpenRegister's region shape (REQ-IOD-001)

anonymiq SHALL serve `POST /api/v1/image/regions` accepting JSON
`{image, page}`, with `image` a base64 PNG, JPEG, TIFF or WebP and `page` an
integer or null. It SHALL answer 200 with `regions`, a list of
`{page, box: {x, y, w, h}, entityType, confidence}` where `page` echoes the
request, `box` values lie between 0 and 1 relative to the image, `entityType`
is one of `SIGNATURE`, `FACE`, `LICENSE_PLATE`, and `confidence` lies between
0 and 1; and `detector`, with `name`, `version` and `classes` (the classes that
were looked for). An image that cannot be decoded SHALL answer 422 with a
reason; an image over 40 megapixels or a body over 25 MB SHALL answer 413; a
model timeout SHALL answer 503. None of these SHALL answer 200.

#### Scenario: a signature on page 2 is found
- GIVEN the fixture `tests/fixtures/image-regions/signed-letter-p2.png`, labelled with one signature
- WHEN OpenRegister posts it with page 2
- THEN the answer holds one region with `entityType` SIGNATURE, page 2 and a box that overlaps the labelled box by at least 0.5 intersection over union, and `detector.classes` includes SIGNATURE
- Test: pytest `tests/test_image_regions.py::test_a_signature_on_page_two_is_found`

#### Scenario: an undecodable image is not a clean page
- GIVEN a body whose `image` is not a valid image
- WHEN it is posted
- THEN the answer is 422 with a reason, not 200
- Test: pytest `tests/test_image_regions.py::test_an_undecodable_image_is_422`

#### Scenario: the shape is OpenRegister's
- GIVEN the recorded request and response from OpenRegister's `AnonymiqImageRegionsContractTest`
- WHEN anonymiq answers the recorded request
- THEN every key OpenRegister reads is present with its type
- Test: pytest `tests/test_image_regions_contract.py::test_the_answer_matches_openregisters_contract`

### Requirement: A class is offered only when its model is loaded and meets the recall floor (REQ-IOD-002)

For each class anonymiq SHALL load a locally run model at start. A class SHALL
be listed in `detector.classes`, and looked for, only when its model loaded
and its recall on the evaluation corpus met the floor (default 0.9 at the
default confidence of 0.5; settings `IMAGE_REGIONS_RECALL_FLOOR` and
`IMAGE_REGIONS_MIN_CONFIDENCE`). A class not offered SHALL NOT be reported as
found nothing.

#### Scenario: the plate model is missing
- GIVEN the plate model's weights absent at start
- WHEN a page with a car is posted
- THEN `detector.classes` lists SIGNATURE and FACE only, and no LICENSE_PLATE region is returned
- Test: pytest `tests/test_image_regions.py::test_a_missing_model_drops_its_class`

#### Scenario: the corpus test guards the floor
- GIVEN the evaluation corpus and the shipped models
- WHEN the evaluation test runs
- THEN it measures precision and recall per class, fails when any offered class's recall is below the floor, and writes the numbers the `about` answer serves
- Test: pytest `tests/test_image_regions_evaluation.py::test_every_offered_class_meets_the_recall_floor`

### Requirement: The detector says what it is built from and how well it does (REQ-IOD-003)

anonymiq SHALL serve `GET /api/v1/image/regions/about` answering `name`,
`version`, `classes`, `models` (each with `class`, `name`, `version`,
`licence`, `source`, `sha256`) and `evaluation` (the corpus name and version,
and per class `precision` and `recall` at the default confidence). The numbers
SHALL be the ones the evaluation test wrote for the shipped models.

#### Scenario: OpenRegister reports the detector's quality
- GIVEN anonymiq running with the shipped models
- WHEN OpenRegister reads `about`
- THEN it gets each model's licence and sha256 and the precision and recall per class on the named corpus
- Test: pytest `tests/test_image_regions.py::test_about_lists_models_and_evaluation`

### Requirement: An image never outlives its request (REQ-IOD-004)

anonymiq SHALL process the image in memory, SHALL NOT write it to disk, the
database or a log, and SHALL log only the request id, the image size and the
region count. When `ANONYMIQ_API_KEY` is set the route SHALL require it as a
bearer token and answer 401 without it; when it is not set anonymiq SHALL log
one warning at start.

#### Scenario: nothing of the image is logged
- GIVEN a posted image
- WHEN the request is handled at debug log level
- THEN no log record contains the base64 or any byte of the image, and no file was created in the working or temporary directory
- Test: pytest `tests/test_image_regions.py::test_the_image_is_not_logged_or_stored`

#### Scenario: a key is required when configured
- GIVEN `ANONYMIQ_API_KEY` set
- WHEN a request without the key is posted
- THEN the answer is 401
- Test: pytest `tests/test_image_regions.py::test_a_configured_key_is_required`
