# Anonymiq Test Suite

Comprehensive test suite for the new string-based analyze and anonymize endpoints.

## Quick Start

Run the complete automated test suite:

```bash
python run_tests.py
```

This will:
1. ✅ Start API locally with `uv run api.py`
2. 🧪 Run all unit tests for new endpoints
3. 📋 Test existing document endpoints (PDF upload)
4. 🛑 Stop local API
5. 🐳 Build Docker container
6. 🧪 Test Docker container endpoints
7. 📊 Generate test report
8. 🚀 Suggest PR creation if all tests pass

## Manual Testing

### Run Individual Test Categories

```bash
# Run only string endpoint tests
uv run pytest tests/test_string_endpoints.py::TestAnalyzeEndpoint -v

# Run only document tests  
uv run pytest tests/test_string_endpoints.py::TestDocumentEndpoints -v

# Run performance tests
uv run pytest tests/test_string_endpoints.py::TestPerformance -v
```

### Start API Manually

```bash
# Start API
uv run api.py

# In another terminal, run tests
uv run pytest tests/test_string_endpoints.py -v

# Stop API (Ctrl+C)
```

## Test Coverage

### New String Endpoints
- ✅ **POST /api/v1/analyze**
  - Basic text analysis with Dutch PII
  - Engine selection (spacy/transformers)  
  - Entity filtering
  - Position information (start/end)
  - Score handling (model-dependent)
  - Input validation

- ✅ **POST /api/v1/anonymize**
  - Text anonymization with different strategies
  - Entity filtering
  - Original vs anonymized text comparison
  - Processing time tracking
  - Input/strategy validation

### Existing Endpoints
- ✅ **GET /api/v1/health** - Health check
- ✅ **POST /api/v1/documents/upload** - PDF upload with analysis

### Error Handling
- ✅ Malformed JSON requests
- ✅ Missing required fields
- ✅ Invalid language codes
- ✅ Invalid anonymization strategies
- ✅ Empty text validation

### Performance
- ✅ Response time validation (<10s)
- ✅ Large text handling
- ✅ Processing time reporting

### Integration
- ✅ Docker container build and test
- ✅ Endpoint consistency checks
- ✅ API availability validation

## Test Reports

After running tests, check:
- `test_report.json` - Machine-readable results
- `test_report.md` - Human-readable summary

## Requirements

The test suite automatically installs:
- `pytest` - Test framework
- `httpx` - HTTP client for API testing

## Test Data

- `test.pdf` - Sample PDF for document upload tests (in project root)

## Debugging Failed Tests

1. **API Won't Start**: Check if port 8080 is already in use
2. **Tests Timeout**: Increase wait times in test runner
3. **Docker Issues**: Ensure Docker is running and accessible
4. **PDF Tests Fail**: Verify `test.pdf` exists in project root

## CI/CD Integration

This test suite is designed for:
1. **Local Development**: Run before committing
2. **Docker Testing**: Validate containerized deployment  
3. **Staging Deployment**: Automated via `run_tests.py`
4. **Production Readiness**: Full integration validation

## Exit Codes

- `0` - All tests passed, ready for deployment
- `1` - Tests failed, fix required before deployment