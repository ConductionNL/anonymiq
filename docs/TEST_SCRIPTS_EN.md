# Anonymiq String Endpoints Test Scripts

Two standalone test scripts for testing the new string-based `/analyze` and `/anonymize` endpoints.

## 🚀 Quick Start

### Option 1: Python Script (Recommended)
```bash
# Start API first
uv run api.py

# Run tests (in another terminal)
python tests/integration/test_endpoints.py
```

### Option 2: Bash Script
```bash
# Start API first
uv run api.py

# Run tests (in another terminal)
./scripts/test_endpoints.sh
```

### Option 3: Test Against Remote Server
```bash
# Test against specific URL
python tests/integration/test_endpoints.py https://api.openanonymiser.commonground.nu
./scripts/test_endpoints.sh https://api.openanonymiser.commonground.nu
```

## 📋 What Gets Tested

### ✅ Health Check
- `GET /api/v1/health` → `{"ping": "pong"}`

### ✅ Analyze Endpoint (`POST /api/v1/analyze`)
- Basic text analysis - Dutch PII detection
- Entity filtering - Only detect specified entity types  
- Engine selection - SpaCy vs Transformers
- Input validation - Empty text, unsupported languages

### ✅ Anonymize Endpoint (`POST /api/v1/anonymize`)
- Basic anonymization - Replace PII with placeholders
- Strategy selection - Different anonymization methods
- Entity filtering - Only anonymize specific types
- Input validation - Invalid strategies

### ✅ Error Handling
- Malformed JSON requests
- Missing required fields
- HTTP error codes (422, 500)

### ✅ Document Upload (Bonus)
- PDF upload test (if `test.pdf` exists)

## 📊 Output Example

```
🚀 Anonymiq String Endpoints Test Suite
Testing against: http://localhost:8080

🔍 Testing Health Check
✅ PASS - Health endpoint

🔍 Testing /analyze Endpoint  
✅ PASS - Analyze basic text
✅ PASS - Analyze with entity filtering
✅ PASS - Analyze with engine selection
✅ PASS - Analyze empty text validation
✅ PASS - Analyze unsupported language

🔍 Testing /anonymize Endpoint
✅ PASS - Anonymize basic text
✅ PASS - Anonymize with strategy
✅ PASS - Anonymize with entity filtering
✅ PASS - Anonymize invalid strategy

📊 Test Results Summary
=================================
Total tests: 12
Passed: 12
Failed: 0

🎉 All tests passed!
```

## 🔧 Requirements

### Python Script
- Python 3.6+
- `requests` library: `pip install requests`

### Bash Script  
- Bash shell
- `curl` command
- `jq` (optional, for prettier JSON)

## 💡 Usage Tips

### Development Workflow
```bash
# 1. Start API in development mode
uv run api.py &

# 2. Run tests after changes
python tests/integration/test_endpoints.py

# 3. Stop API
kill %1
```

### Docker Testing
```bash
# 1. Build and run container
docker build -t anonymiq:test .
docker run -d -p 8081:8080 anonymiq:test

# 2. Test container
python tests/integration/test_endpoints.py http://localhost:8081

# 3. Cleanup
docker stop $(docker ps -q --filter ancestor=anonymiq:test)
```

### CI/CD Integration
```bash
#!/bin/bash
# Add to your CI pipeline

# Start API in background
uv run api.py --env production &
API_PID=$!

# Wait for startup
sleep 10

# Run tests
python tests/integration/test_endpoints.py

# Capture exit code
TEST_EXIT_CODE=$?

# Cleanup
kill $API_PID

# Exit with test result
exit $TEST_EXIT_CODE
```

## 🆚 Script Comparison

| Feature | Python Script | Bash Script |
|---------|---------------|-------------|
| **Cross-platform** | ✅ Windows/Mac/Linux | ❌ Unix only |
| **JSON handling** | ✅ Native | ⚠️ String parsing |
| **Error details** | ✅ Rich output | ✅ Basic output |
| **Dependencies** | `requests` | `curl` |
| **Speed** | ⚡ Fast | ⚡ Fast |
| **Readability** | ✅ Structured | ✅ Simple |

## 🚀 Exit Codes

- `0` - All tests passed
- `1` - Some tests failed  
- `1` - API not available

Perfect for CI/CD pipelines and automated testing!

