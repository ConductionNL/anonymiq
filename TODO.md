# Anonymiq Development Roadmap

## 🚀 Current Status
✅ **Application successfully deployed and running externally**
- Pod health checks passing (200 OK)
- External access working via `http://api.openanonymiser.commonground.nu`
- Network policy issue resolved
- Docker image v1.0.8 stable

---

## 🎯 Theme 1: Stabiliteit & CI/CD Pipeline

### 1.1 Testing Infrastructure
- [ ] **Unit Tests**
  - [ ] Test coverage for all core functions in `src/api/`
  - [ ] Test database models and relationships
  - [ ] Test configuration management
  - [ ] Test utility functions (PDF processing, encryption)
  - [ ] Aim for >80% code coverage

- [ ] **Integration Tests**
  - [ ] API endpoint tests (health, document upload/download)
  - [ ] Database integration tests
  - [ ] File handling and storage tests
  - [ ] Authentication/authorization tests
  - [ ] Cross-service communication tests

- [ ] **End-to-End Tests**
  - [ ] Full document anonymization workflow
  - [ ] Multi-format document processing (PDF, DOCX, TXT)
  - [ ] Error handling scenarios
  - [ ] Performance tests with large documents

### 1.2 CI/CD Pipeline (GitHub Actions)
- [ ] **Build Pipeline** (`.github/workflows/build.yml`)
  - [ ] Trigger on push to `main` and PRs
  - [ ] Multi-stage Docker build with caching
  - [ ] Security scanning (Trivy/Snyk)
  - [ ] Image vulnerability assessment
  - [ ] Tag images with commit SHA and semantic versions

- [ ] **Test Pipeline** (`.github/workflows/test.yml`)
  - [ ] Run unit tests with pytest
  - [ ] Run integration tests
  - [ ] Code quality checks (ruff, black, mypy)
  - [ ] Test coverage reporting
  - [ ] Performance benchmarks

- [ ] **Deploy Pipeline** (`.github/workflows/deploy.yml`)
  - [ ] Deploy to staging environment first
  - [ ] Run smoke tests against staging
  - [ ] Deploy to production (ArgoCD integration)
  - [ ] Health check validation
  - [ ] Rollback capability

### 1.3 Code Quality & Maintenance
- [ ] **Linting & Formatting**
  - [ ] Configure pre-commit hooks
  - [ ] Ruff for linting
  - [ ] Black for code formatting
  - [ ] MyPy for type checking
  - [ ] isort for import sorting

- [ ] **Dependency Management**
  - [ ] Automated dependency updates (Dependabot)
  - [ ] Security vulnerability scanning
  - [ ] License compliance checking
  - [ ] Clean up unused dependencies

- [ ] **File Cleanup & Organization**
  - [ ] Remove temporary/debug files
  - [ ] Organize project structure
  - [ ] Clean up Docker build context
  - [ ] Optimize .dockerignore and .gitignore

---

## 📚 Theme 2: Documentatie & Developer Experience

### 2.1 API Documentation
- [ ] **Interactive Documentation**
  - [ ] Enhance FastAPI OpenAPI/Swagger docs
  - [ ] Add comprehensive endpoint examples
  - [ ] Request/response schemas with examples
  - [ ] Authentication flow documentation
  - [ ] Error code reference

- [ ] **Developer Portal** (Docusaurus or MkDocs)
  - [ ] Getting started guide
  - [ ] API reference with code samples
  - [ ] Authentication setup
  - [ ] Deployment instructions
  - [ ] Contributing guidelines

### 2.2 Database Documentation
- [ ] **Entity Relationship Diagram (ERD)**
  - [ ] Visual database schema
  - [ ] Table relationships
  - [ ] Data flow diagrams
  - [ ] Migration history

- [ ] **Database Documentation**
  - [ ] Table descriptions and purposes
  - [ ] Column specifications and constraints  
  - [ ] Index strategies
  - [ ] Backup and recovery procedures

### 2.3 Architecture Documentation
- [ ] **System Architecture**
  - [ ] Component diagrams
  - [ ] Data flow documentation
  - [ ] Security architecture
  - [ ] Kubernetes deployment architecture

- [ ] **Code Examples & Tutorials**
  - [ ] Python client examples
  - [ ] cURL examples for all endpoints
  - [ ] JavaScript/TypeScript SDK
  - [ ] Integration examples (React, Node.js)

---

## 🔧 Theme 3: Nieuwe API Endpoints

### 3.1 String-based Analysis Endpoints
- [ ] **POST /api/v1/analyze** 
  - [ ] Accept JSON payload with text string
  - [ ] Return PII detection results using Presidio framework
  - [ ] Support different analysis engines (spaCy, Transformers)
  - [ ] Configurable confidence thresholds
  - [ ] **Include scores when available** (model-dependent)
  - [ ] Response format with optional scores:
  ```json
  {
    "pii_entities": [
      {
        "entity_type": "PERSON",
        "text": "Jan de Vries",
        "score": 0.9999995231628418
      },
      {
        "entity_type": "LOCATION", 
        "text": "Amsterdam",
        "score": 0.9999994039535522
      }
    ]
  }
  ```

- [ ] **POST /api/v1/anonymize**
  - [ ] Accept JSON payload with text string
  - [ ] Return anonymized text using Presidio framework
  - [ ] Support different anonymization strategies
  - [ ] Preserve original formatting where possible
  - [ ] Response format consistent with Presidio:
  ```json
  {
    "original_text": "Mijn naam is Jan de Vries, mijn BSN is 123456789 en ik woon in Amsterdam.",
    "anonymized_text": "Mijn naam is [PERSOON], mijn [PERSOON] is 123456789 en ik woon in [LOCATIE].",
    "entities_found": [
      {
        "entity_type": "PERSON",
        "text": "Jan de Vries",
        "score": 0.9999995231628418
      },
      {
        "entity_type": "LOCATION",
        "text": "Amsterdam", 
        "score": 0.9999994039535522
      }
    ]
  }
  ```

### 3.2 Enhanced Features
- [ ] **Multi-Model Support & Documentation**
  - [ ] Create `/docs/models/` documentation section
  - [ ] Document score support per model:
    - ✅ **TransformersEngine**: Scores available (Hugging Face confidence)
    - ❌ **SpacyEngine**: No scores (returns empty string)
    - ✅ **Presidio Pattern Recognizers**: Scores available (confidence)
  - [ ] Model comparison documentation
  - [ ] Performance benchmarks per model
  - [ ] Model selection guidelines

- [ ] **Presidio-Research Integration**
  - [ ] Research presidio-research capabilities for benchmarking
  - [ ] Implement automated model evaluation and benchmarking
  - [ ] Set up performance comparison pipelines
  - [ ] Create evaluation datasets for Dutch PII detection
  - [ ] Generate model accuracy reports and metrics
  - [ ] Integrate benchmarking results into documentation
  - [ ] Automated model selection based on performance metrics

- [ ] **Batch Processing**
  - [ ] POST /api/v1/analyze/batch (multiple texts)
  - [ ] POST /api/v1/anonymize/batch (multiple texts)
  - [ ] Async processing for large batches
  - [ ] Progress tracking endpoints

- [ ] **Configuration Options**
  - [ ] Customizable anonymization rules
  - [ ] Language-specific processing
  - [ ] Entity type filtering
  - [ ] Output format options (JSON, plain text)
  - [ ] Model selection per request

### 3.3 Backwards Compatibility
- [ ] **Document Endpoints Enhancement**
  - [ ] Maintain existing document upload/download functionality (NO scores)
  - [ ] New endpoints use `entities` list WITH scores when available
  - [ ] Existing endpoints use `unique` list WITHOUT scores (unchanged)
  - [ ] Add metadata response for processed documents
  - [ ] Link document processing with string analysis results
  - [ ] Consistent response formats across all endpoints

- [ ] **Score Handling Strategy**
  - [ ] Existing `/documents/upload/`: Keep current format (no scores)
  - [ ] New `/analyze` & `/anonymize`: Include scores when model supports it
  - [ ] Document score availability per model in API docs
  - [ ] Graceful handling when scores not available

---

## 🚀 Release Planning

### v1.1.0 - Stability Release
- [ ] Complete Theme 1 (CI/CD + Testing)
- [ ] Basic documentation improvements
- [ ] Security hardening

### v1.2.0 - Feature Release  
- [ ] New string-based endpoints (/analyze, /anonymize)
- [ ] Enhanced documentation portal
- [ ] Performance improvements

### v1.3.0 - Production Release
- [ ] Full monitoring stack
- [ ] SSL/TLS enabled
- [ ] Scalability features
- [ ] Complete documentation

---

## 📝 Notes

**Priority Order:**
1. **Theme 3** - Core feature requirements (analyze/anonymize endpoints)
2. **Theme 1** - Critical for production stability  
3. **Theme 2** - Developer experience

**Current Focus:**
- **Theme 3** - Implementing `/analyze` and `/anonymize` endpoints
- These endpoints accept string input instead of file uploads
- Same functionality as document processing but for text strings
- **Consistent response format** with existing /documents/upload/ endpoint
- **Using Presidio framework** for PII detection and anonymization

---

*Last updated: 2025-07-30*
*Current version: v1.0.8*
*Status: ✅ Deployed and externally accessible*
*Next: Working on Theme 3 - String-based endpoints*