#!/bin/bash

# Anonymiq String Endpoints Test Script
# Usage: ./test_endpoints.sh [base_url]

BASE_URL="${1:-http://localhost:8080}"
PASSED=0
FAILED=0
TOTAL=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_test() {
    local test_name="$1"
    local status="$2"
    local details="$3"
    
    TOTAL=$((TOTAL + 1))
    
    if [ "$status" = "PASS" ]; then
        echo -e "${GREEN}✅ PASS${NC} - $test_name"
        PASSED=$((PASSED + 1))
    else
        echo -e "${RED}❌ FAIL${NC} - $test_name"
        if [ -n "$details" ]; then
            echo -e "   ${YELLOW}Details:${NC} $details"
        fi
        FAILED=$((FAILED + 1))
    fi
}

test_health() {
    echo -e "\n${BLUE}🔍 Testing Health Check${NC}"
    
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" "$BASE_URL/api/v1/health")
    http_code=$(echo "$response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    body=$(echo "$response" | sed -e 's/HTTPSTATUS\:.*//g')
    
    if [ "$http_code" = "200" ] && echo "$body" | grep -q '"ping":"pong"'; then
        log_test "Health endpoint" "PASS"
    else
        log_test "Health endpoint" "FAIL" "HTTP $http_code, Body: $body"
    fi
}

test_analyze() {
    echo -e "\n${BLUE}🔍 Testing /analyze Endpoint${NC}"
    
    # Test 1: Basic text analysis
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "$BASE_URL/api/v1/analyze" \
        -H "Content-Type: application/json" \
        -d '{"text": "Jan de Vries woont in Amsterdam", "language": "nl"}')
    
    http_code=$(echo "$response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    body=$(echo "$response" | sed -e 's/HTTPSTATUS\:.*//g')
    
    if [ "$http_code" = "200" ] && echo "$body" | grep -q '"pii_entities"' && echo "$body" | grep -q '"PERSON"'; then
        log_test "Analyze basic text" "PASS"
    else
        log_test "Analyze basic text" "FAIL" "HTTP $http_code, Body: $body"
    fi
    
    # Test 2: Entity filtering
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "$BASE_URL/api/v1/analyze" \
        -H "Content-Type: application/json" \
        -d '{"text": "Jan de Vries woont in Amsterdam", "language": "nl", "entities": ["PERSON"]}')
    
    http_code=$(echo "$response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    body=$(echo "$response" | sed -e 's/HTTPSTATUS\:.*//g')
    
    if [ "$http_code" = "200" ] && echo "$body" | grep -q '"PERSON"'; then
        log_test "Analyze with entity filtering" "PASS"
    else
        log_test "Analyze with entity filtering" "FAIL" "HTTP $http_code, Body: $body"
    fi
    
    # Test 3: Engine selection
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "$BASE_URL/api/v1/analyze" \
        -H "Content-Type: application/json" \
        -d '{"text": "Maria woont in Utrecht", "language": "nl", "nlp_engine": "spacy"}')
    
    http_code=$(echo "$response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    body=$(echo "$response" | sed -e 's/HTTPSTATUS\:.*//g')
    
    if [ "$http_code" = "200" ] && echo "$body" | grep -q '"nlp_engine_used":"spacy"'; then
        log_test "Analyze with engine selection" "PASS"
    else
        log_test "Analyze with engine selection" "FAIL" "HTTP $http_code, Body: $body"
    fi
    
    # Test 4: Empty text validation
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "$BASE_URL/api/v1/analyze" \
        -H "Content-Type: application/json" \
        -d '{"text": "", "language": "nl"}')
    
    http_code=$(echo "$response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    
    if [ "$http_code" = "422" ]; then
        log_test "Analyze empty text validation" "PASS"
    else
        log_test "Analyze empty text validation" "FAIL" "Expected HTTP 422, got $http_code"
    fi
    
    # Test 5: Unsupported language
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "$BASE_URL/api/v1/analyze" \
        -H "Content-Type: application/json" \
        -d '{"text": "Hello world", "language": "fr"}')
    
    http_code=$(echo "$response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    
    if [ "$http_code" = "422" ]; then
        log_test "Analyze unsupported language" "PASS"
    else
        log_test "Analyze unsupported language" "FAIL" "Expected HTTP 422, got $http_code"
    fi
}

test_anonymize() {
    echo -e "\n${BLUE}🔍 Testing /anonymize Endpoint${NC}"
    
    # Test 1: Basic anonymization
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "$BASE_URL/api/v1/anonymize" \
        -H "Content-Type: application/json" \
        -d '{"text": "Jan de Vries woont in Amsterdam", "language": "nl"}')
    
    http_code=$(echo "$response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    body=$(echo "$response" | sed -e 's/HTTPSTATUS\:.*//g')
    
    if [ "$http_code" = "200" ] && echo "$body" | grep -q '"original_text"' && echo "$body" | grep -q '"anonymized_text"'; then
        log_test "Anonymize basic text" "PASS"
    else
        log_test "Anonymize basic text" "FAIL" "HTTP $http_code, Body: $body"
    fi
    
    # Test 2: Strategy specification
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "$BASE_URL/api/v1/anonymize" \
        -H "Content-Type: application/json" \
        -d '{"text": "Jan woont in Amsterdam", "language": "nl", "anonymization_strategy": "replace"}')
    
    http_code=$(echo "$response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    body=$(echo "$response" | sed -e 's/HTTPSTATUS\:.*//g')
    
    if [ "$http_code" = "200" ] && echo "$body" | grep -q '"anonymization_strategy":"replace"'; then
        log_test "Anonymize with strategy" "PASS"
    else
        log_test "Anonymize with strategy" "FAIL" "HTTP $http_code, Body: $body"
    fi
    
    # Test 3: Entity filtering
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "$BASE_URL/api/v1/anonymize" \
        -H "Content-Type: application/json" \
        -d '{"text": "Jan de Vries woont in Amsterdam", "language": "nl", "entities": ["PERSON"]}')
    
    http_code=$(echo "$response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    body=$(echo "$response" | sed -e 's/HTTPSTATUS\:.*//g')
    
    if [ "$http_code" = "200" ] && echo "$body" | grep -q "Amsterdam"; then
        log_test "Anonymize with entity filtering" "PASS"
    else
        log_test "Anonymize with entity filtering" "FAIL" "HTTP $http_code, Body: $body"
    fi
    
    # Test 4: Invalid strategy
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "$BASE_URL/api/v1/anonymize" \
        -H "Content-Type: application/json" \
        -d '{"text": "Jan woont in Amsterdam", "language": "nl", "anonymization_strategy": "invalid_strategy"}')
    
    http_code=$(echo "$response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    
    if [ "$http_code" = "422" ]; then
        log_test "Anonymize invalid strategy" "PASS"
    else
        log_test "Anonymize invalid strategy" "FAIL" "Expected HTTP 422, got $http_code"
    fi
}

test_error_handling() {
    echo -e "\n${BLUE}🔍 Testing Error Handling${NC}"
    
    # Test 1: Malformed JSON
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "$BASE_URL/api/v1/analyze" \
        -H "Content-Type: application/json" \
        -d '{"text": "test", "language":')
    
    http_code=$(echo "$response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    
    if [ "$http_code" = "422" ]; then
        log_test "Malformed JSON handling" "PASS"
    else
        log_test "Malformed JSON handling" "FAIL" "Expected HTTP 422, got $http_code"
    fi
    
    # Test 2: Missing required fields
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "$BASE_URL/api/v1/analyze" \
        -H "Content-Type: application/json" \
        -d '{"language": "nl"}')
    
    http_code=$(echo "$response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    
    if [ "$http_code" = "422" ]; then
        log_test "Missing required fields" "PASS"
    else
        log_test "Missing required fields" "FAIL" "Expected HTTP 422, got $http_code"
    fi
}

# Main execution
main() {
    echo -e "${BLUE}🚀 Anonymiq String Endpoints Test Suite${NC}"
    echo -e "${BLUE}Testing against: $BASE_URL${NC}"
    echo ""
    
    # Check if API is running
    if ! curl -s "$BASE_URL/api/v1/health" > /dev/null; then
        echo -e "${RED}❌ API is not running at $BASE_URL${NC}"
        echo "Please start the API first with: uv run api.py"
        exit 1
    fi
    
    test_health
    test_analyze
    test_anonymize
    test_error_handling
    
    echo -e "\n${BLUE}📊 Test Results Summary${NC}"
    echo "================================="
    echo -e "Total tests: $TOTAL"
    echo -e "${GREEN}Passed: $PASSED${NC}"
    echo -e "${RED}Failed: $FAILED${NC}"
    
    if [ $FAILED -eq 0 ]; then
        echo -e "\n${GREEN}🎉 All tests passed!${NC}"
        exit 0
    else
        echo -e "\n${RED}⚠️ Some tests failed.${NC}"
        exit 1
    fi
}

main "$@"