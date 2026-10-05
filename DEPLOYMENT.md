# Anonymiq Deployment Guide

## 🚀 GitOps Workflow Overview

**Simplified deployment without staging/development branches:**

```
Feature Branch → Test & Tag → Staging Deployment → Production
```

## 📋 Deployment Options

### 1. **Feature Branch Development** (Current)
```bash
# Work on feature branch
git checkout feature/string-endpoints
git push origin feature/string-endpoints

# This triggers:
# ✅ Unit tests (feature-testing.yml, pytest tests/unit)
# Only when the repository variable PUBLISH_FEATURE_IMAGES=true:
# ✅ Docker image build and the 'dev' tag (staging pulls 'dev')
```

### 2. **Manual Staging Deployment** 
```bash
# Via GitHub Actions UI:
# Go to Actions → "Deploy Feature to Staging" → Run workflow
# Select branch: feature/string-endpoints
# Environment: staging
```

### 3. **Production Deployment**
```bash
# Merge to main triggers full production deployment
git checkout main
git merge feature/string-endpoints
git push origin main

# This triggers:
# ✅ Full test suite
# ✅ Production Docker build with versioning
# ✅ SSL enabled + HTTPS redirect
# ✅ GitHub release creation
```

## 🎯 Current Workflow Status

### ✅ **Working Now:**
- Local testing: `python tests/integration/test_endpoints.py`
- Docker testing: Container builds and tests pass
- Auto-tagging: `dev` tag created on successful tests
- Manual staging deployment: Available via GitHub Actions

### ⏳ **In Progress:**
- ArgoCD sync for staging deployment
- Cloud API testing

### 🔄 **Available Workflows:**

#### `feature-testing.yml` - Auto-testing & Tagging
- **Trigger:** Push to any feature branch, and pull requests to main or development
- **Actions:** Unit tests (`pytest tests/unit`); building images and moving the `dev` tag only with the repository variable `PUBLISH_FEATURE_IMAGES=true`
- **Perfect for:** Development workflow

#### `deploy-staging.yml` - Manual Staging Deploy  
- **Trigger:** Manual (GitHub Actions UI)
- **Actions:** Build → Deploy → Test cloud API
- **Perfect for:** Staging validation

#### `deploy-production.yml` - Production Deploy
- **Trigger:** Push to `main` branch
- **Actions:** Full tests → Build → Deploy → SSL → Release
- **Perfect for:** Production releases

## 🏷️ Image Tagging Strategy

```bash
# Feature development
mwest2020/openanonymiser:dev                    # Latest working version
mwest2020/openanonymiser:feature-string-endpoints  # Feature-specific

# Staging deployment  
mwest2020/openanonymiser:staging-string-endpoints-20250801-abc1234

# Production deployment
mwest2020/openanonymiser:v1.1.0                # Versioned release
mwest2020/openanonymiser:latest                # Latest production
```

## 🧪 Testing Commands

### Local Testing
```bash
uv run api.py &
python tests/integration/test_endpoints.py
./scripts/test_endpoints.sh
```

### Cloud Testing
```bash
python tests/integration/test_endpoints.py https://api.openanonymiser.commonground.nu
./scripts/test_endpoints.sh https://api.openanonymiser.commonground.nu
```

### Docker Testing
```bash
docker run -d -p 8081:8080 mwest2020/openanonymiser:dev
python tests/integration/test_endpoints.py http://localhost:8081
```

## 🔧 Manual Cluster Operations

### Deploy Latest Dev Image
```bash
kubectl set image deployment/openanonymiser \
  openanonymiser=mwest2020/openanonymiser:dev \
  -n openanonymiser
```

### Check Deployment Status
```bash
kubectl get pods -n openanonymiser
kubectl describe deployment openanonymiser -n openanonymiser
kubectl logs -l app=openanonymiser -n openanonymiser --tail=50
```

### Force ArgoCD Sync
```bash
argocd app sync openanonymiser
# Or via ArgoCD UI
```

## 🎊 Ready for Production?

**When all tests pass:**
1. **Merge feature branch to main**
2. **Production workflow automatically triggers**
3. **SSL + versioned release created**
4. **Cloud API tests validate production**

**Current Status:** ✅ Feature complete, staging deployment in progress!