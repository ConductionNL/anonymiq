#!/usr/bin/env python3
"""
Anonymiq String Endpoints Test Script
Usage: python test_endpoints.py [base_url]
"""

import sys
import json
import requests
from typing import Dict, Any
import time

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"


class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    NC = "\033[0m"  # No Color


class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0

    def log_test(self, test_name: str, status: str, details: str = ""):
        """Log test result with colored output."""
        self.total += 1

        if status == "PASS":
            print(f"{Colors.GREEN}✅ PASS{Colors.NC} - {test_name}")
            self.passed += 1
        else:
            print(f"{Colors.RED}❌ FAIL{Colors.NC} - {test_name}")
            if details:
                print(f"   {Colors.YELLOW}Details:{Colors.NC} {details}")
            self.failed += 1

    def make_request(
        self,
        method: str,
        endpoint: str,
        data: Dict[Any, Any] = None,
        expected_status: int = 200,
    ) -> Dict[str, Any]:
        """Make HTTP request and return response details."""
        url = f"{BASE_URL}{endpoint}"
        try:
            if method == "GET":
                response = requests.get(url, timeout=30)
            elif method == "POST":
                response = requests.post(url, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")

            return {
                "status_code": response.status_code,
                "json": response.json()
                if response.headers.get("content-type", "").startswith(
                    "application/json"
                )
                else None,
                "text": response.text,
                "success": response.status_code == expected_status,
            }
        except requests.exceptions.RequestException as e:
            return {"status_code": 0, "json": None, "text": str(e), "success": False}
        except json.JSONDecodeError:
            return {
                "status_code": response.status_code,
                "json": None,
                "text": response.text,
                "success": response.status_code == expected_status,
            }

    def test_health(self):
        """Test health endpoint."""
        print(f"\n{Colors.BLUE}🔍 Testing Health Check{Colors.NC}")

        response = self.make_request("GET", "/api/v1/health")

        if (
            response["success"]
            and response["json"]
            and response["json"].get("ping") == "pong"
        ):
            self.log_test("Health endpoint", "PASS")
        else:
            self.log_test(
                "Health endpoint",
                "FAIL",
                f"HTTP {response['status_code']}, Body: {response['text']}",
            )

    def test_analyze(self):
        """Test /analyze endpoint."""
        print(f"\n{Colors.BLUE}🔍 Testing /analyze Endpoint{Colors.NC}")

        # Test 1: Basic text analysis
        data = {"text": "Jan de Vries woont in Amsterdam", "language": "nl"}
        response = self.make_request("POST", "/api/v1/analyze", data)

        if (
            response["success"]
            and response["json"]
            and "pii_entities" in response["json"]
            and any(
                entity.get("entity_type") == "PERSON"
                for entity in response["json"]["pii_entities"]
            )
        ):
            self.log_test("Analyze basic text", "PASS")
        else:
            self.log_test(
                "Analyze basic text",
                "FAIL",
                f"HTTP {response['status_code']}, Response: {response['text'][:200]}",
            )

        # Test 2: Entity filtering
        data = {
            "text": "Jan de Vries woont in Amsterdam",
            "language": "nl",
            "entities": ["PERSON"],
        }
        response = self.make_request("POST", "/api/v1/analyze", data)

        if (
            response["success"]
            and response["json"]
            and any(
                entity.get("entity_type") == "PERSON"
                for entity in response["json"]["pii_entities"]
            )
        ):
            self.log_test("Analyze with entity filtering", "PASS")
        else:
            self.log_test(
                "Analyze with entity filtering",
                "FAIL",
                f"HTTP {response['status_code']}, Response: {response['text'][:200]}",
            )

        # Test 3: Engine selection
        data = {
            "text": "Maria woont in Utrecht",
            "language": "nl",
            "nlp_engine": "spacy",
        }
        response = self.make_request("POST", "/api/v1/analyze", data)

        if (
            response["success"]
            and response["json"]
            and response["json"].get("nlp_engine_used") == "spacy"
        ):
            self.log_test("Analyze with engine selection", "PASS")
        else:
            self.log_test(
                "Analyze with engine selection",
                "FAIL",
                f"HTTP {response['status_code']}, Response: {response['text'][:200]}",
            )

        # Test 4: Empty text validation
        data = {"text": "", "language": "nl"}
        response = self.make_request(
            "POST", "/api/v1/analyze", data, expected_status=422
        )

        if response["status_code"] == 422:
            self.log_test("Analyze empty text validation", "PASS")
        else:
            self.log_test(
                "Analyze empty text validation",
                "FAIL",
                f"Expected HTTP 422, got {response['status_code']}",
            )

        # Test 5: Unsupported language
        data = {"text": "Hello world", "language": "fr"}
        response = self.make_request(
            "POST", "/api/v1/analyze", data, expected_status=422
        )

        if response["status_code"] == 422:
            self.log_test("Analyze unsupported language", "PASS")
        else:
            self.log_test(
                "Analyze unsupported language",
                "FAIL",
                f"Expected HTTP 422, got {response['status_code']}",
            )

    def test_anonymize(self):
        """Test /anonymize endpoint."""
        print(f"\n{Colors.BLUE}🔍 Testing /anonymize Endpoint{Colors.NC}")

        # Test 1: Basic anonymization
        data = {"text": "Jan de Vries woont in Amsterdam", "language": "nl"}
        response = self.make_request("POST", "/api/v1/anonymize", data)

        if (
            response["success"]
            and response["json"]
            and "original_text" in response["json"]
            and "anonymized_text" in response["json"]
        ):
            self.log_test("Anonymize basic text", "PASS")
        else:
            self.log_test(
                "Anonymize basic text",
                "FAIL",
                f"HTTP {response['status_code']}, Response: {response['text'][:200]}",
            )

        # Test 2: Strategy specification
        data = {
            "text": "Jan woont in Amsterdam",
            "language": "nl",
            "anonymization_strategy": "replace",
        }
        response = self.make_request("POST", "/api/v1/anonymize", data)

        if (
            response["success"]
            and response["json"]
            and response["json"].get("anonymization_strategy") == "replace"
        ):
            self.log_test("Anonymize with strategy", "PASS")
        else:
            self.log_test(
                "Anonymize with strategy",
                "FAIL",
                f"HTTP {response['status_code']}, Response: {response['text'][:200]}",
            )

        # Test 3: Entity filtering
        data = {
            "text": "Jan de Vries woont in Amsterdam",
            "language": "nl",
            "entities": ["PERSON"],
        }
        response = self.make_request("POST", "/api/v1/anonymize", data)

        if (
            response["success"]
            and response["json"]
            and "Amsterdam" in response["json"].get("anonymized_text", "")
        ):
            self.log_test("Anonymize with entity filtering", "PASS")
        else:
            self.log_test(
                "Anonymize with entity filtering",
                "FAIL",
                f"HTTP {response['status_code']}, Response: {response['text'][:200]}",
            )

        # Test 4: Invalid strategy
        data = {
            "text": "Jan woont in Amsterdam",
            "language": "nl",
            "anonymization_strategy": "invalid_strategy",
        }
        response = self.make_request(
            "POST", "/api/v1/anonymize", data, expected_status=422
        )

        if response["status_code"] == 422:
            self.log_test("Anonymize invalid strategy", "PASS")
        else:
            self.log_test(
                "Anonymize invalid strategy",
                "FAIL",
                f"Expected HTTP 422, got {response['status_code']}",
            )

    def test_error_handling(self):
        """Test error handling scenarios."""
        print(f"\n{Colors.BLUE}🔍 Testing Error Handling{Colors.NC}")

        # Test 1: Missing required fields
        data = {"language": "nl"}  # Missing 'text' field
        try:
            requests.post(f"{BASE_URL}/api/v1/analyze", json=data, timeout=30)
        except:
            pass

        response = requests.post(f"{BASE_URL}/api/v1/analyze", json=data, timeout=30)
        if response.status_code == 422:
            self.log_test("Missing required fields", "PASS")
        else:
            self.log_test(
                "Missing required fields",
                "FAIL",
                f"Expected HTTP 422, got {response.status_code}",
            )

    def test_document_upload(self):
        """Test document upload endpoint (if test.pdf exists)."""
        print(f"\n{Colors.BLUE}🔍 Testing Document Upload{Colors.NC}")

        import os

        if not os.path.exists("test.pdf"):
            self.log_test("Document upload", "SKIP", "test.pdf not found")
            return

        try:
            with open("test.pdf", "rb") as f:
                files = {"files": ("test.pdf", f, "application/pdf")}
                response = requests.post(
                    f"{BASE_URL}/api/v1/documents/upload", files=files, timeout=30
                )

            if response.status_code == 200:
                data = response.json()
                if "files" in data and len(data["files"]) > 0:
                    self.log_test("Document upload", "PASS")
                else:
                    self.log_test("Document upload", "FAIL", "No files in response")
            else:
                self.log_test("Document upload", "FAIL", f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test("Document upload", "FAIL", str(e))

    def check_api_availability(self):
        """Check if API is running."""
        try:
            response = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
            return response.status_code == 200
        except:
            return False

    def run_all_tests(self):
        """Run all tests and report results."""
        print(f"{Colors.BLUE}🚀 Anonymiq String Endpoints Test Suite{Colors.NC}")
        print(f"{Colors.BLUE}Testing against: {BASE_URL}{Colors.NC}")
        print()

        # Check API availability
        if not self.check_api_availability():
            print(f"{Colors.RED}❌ API is not running at {BASE_URL}{Colors.NC}")
            print("Please start the API first with: uv run api.py")
            sys.exit(1)

        # Run all tests
        self.test_health()
        self.test_analyze()
        self.test_anonymize()
        self.test_error_handling()
        self.test_document_upload()

        # Report results
        print(f"\n{Colors.BLUE}📊 Test Results Summary{Colors.NC}")
        print("=================================")
        print(f"Total tests: {self.total}")
        print(f"{Colors.GREEN}Passed: {self.passed}{Colors.NC}")
        print(f"{Colors.RED}Failed: {self.failed}{Colors.NC}")

        if self.failed == 0:
            print(f"\n{Colors.GREEN}🎉 All tests passed!{Colors.NC}")
            return True
        else:
            print(f"\n{Colors.RED}⚠️ Some tests failed.{Colors.NC}")
            return False


if __name__ == "__main__":
    runner = TestRunner()
    success = runner.run_all_tests()
    sys.exit(0 if success else 1)
