# Changelog

## [Production-Ready Release] - 2026-02-01

### 🔒 Security Improvements

**Critical Fixes**:
- Fixed XSS vulnerability in React Router (updated to 6.31.0+)
- Replaced deprecated `datetime.utcnow()` with timezone-aware `datetime.now(UTC)` across entire codebase
- Added file upload size validation (10MB for PDFs, 1MB for CSVs, 2MB for images)
- Implemented file type validation for all upload endpoints
- Added security headers middleware (X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, HSTS)
- Configured CORS to be restrictive in production (environment-based)
- Disabled API documentation endpoints in production

**File Upload Security**:
- `/api/floorplan/import-pdf`: PDF validation + 10MB limit
- `/api/floorplan/instances/{id}/export-annotated`: PDF validation + 10MB limit
- `/api/allergens/{key}/icon`: PNG validation + 2MB limit (already implemented)
- `/api/drinks/import/upload`: CSV validation + 1MB limit

### 📦 Dependency Updates

**Backend (Python)**:
- fastapi: 0.115.2 → 0.128.0
- uvicorn: 0.30.6 → 0.40.0
- sqlmodel: 0.0.22 → 0.0.32
- SQLAlchemy: 2.0.36 → 2.0.46
- pydantic: 2.9.2 → 2.12.5
- pydantic-settings: 2.6.1 → 2.12.0
- python-dotenv: 1.0.1 → 1.2.1
- reportlab: 4.2.5 → 4.4.9
- aiofiles: 24.1.0 → 25.1.0
- psycopg2-binary: 2.9.9 → 2.9.11
- Pillow: 10.4.0 → 12.1.0
- pdfminer.six: 20231228 → 20260107
- python-multipart: 0.0.9 → 0.0.22
- requests: 2.32.3 → 2.32.5
- tzdata: 2024.1 → 2025.3
- pypdf: 3.17.4 → 5.2.0

**Frontend (Node)**:
- react-router-dom: 6.26.2 → 6.31.0+ (security fix)
- All other dependencies updated via `npm audit fix`
- Added ESLint, Prettier for code quality

### 🛠️ Code Quality

**Linting & Formatting**:
- Added ESLint configuration with TypeScript support
- Added Prettier configuration for consistent formatting
- Added Flake8 configuration for Python linting
- Created npm scripts: `lint`, `lint:fix`, `format`, `format:check`, `type-check`

**Type Safety**:
- All TypeScript compilation passes without errors
- Strict mode enabled in tsconfig.json
- Proper type annotations throughout codebase

### 🚀 Performance & Optimization

**Build Optimization**:
- Frontend builds successfully (354KB gzipped JS, 8KB gzipped CSS)
- Vite production build optimized
- Static asset serving configured

**Database**:
- Idempotent migrations run automatically on startup
- Proper indexes on frequently queried columns
- Connection pooling configured

### 📝 Documentation

**New Documentation**:
- `README.md`: Comprehensive setup and usage guide
- `DEPLOYMENT.md`: Detailed deployment instructions for Railway, Heroku, Docker, VPS
- `.env.example`: Environment variable template
- `CHANGELOG.md`: This file

**Code Documentation**:
- Inline comments for complex logic
- Docstrings for API endpoints
- Type hints throughout Python code

### 🔧 Configuration

**Environment-Based Config**:
- `ENVIRONMENT` variable controls production/development behavior
- `ALLOWED_ORIGINS` for CORS configuration
- API docs disabled in production
- Security headers enforced in production

**New Files**:
- `.eslintrc.json`: ESLint configuration
- `.prettierrc.json`: Prettier configuration
- `.prettierignore`: Prettier ignore patterns
- `.flake8`: Python linting configuration
- `.env.example`: Environment variable template

### ✅ Testing & Validation

**Build Validation**:
- [x] Frontend builds successfully
- [x] TypeScript compilation passes
- [x] No security vulnerabilities in dependencies
- [x] All deprecated APIs replaced

**Manual Testing Checklist** (see README.md):
- Critical user flows documented
- Browser compatibility requirements specified
- Deployment verification steps provided

### 🐛 Bug Fixes

- Fixed duplicate file reads in CSV upload endpoint
- Fixed timezone issues by migrating to UTC-aware datetime
- Improved error handling in PDF parsing
- Better validation for edge cases in reservations

### 📋 Breaking Changes

**None** - All changes are backward compatible. Existing functionality preserved.

### 🔄 Migration Notes

**For Existing Deployments**:
1. Update environment variables (add `ENVIRONMENT`, `ALLOWED_ORIGINS`)
2. Dependencies will auto-update on next deployment
3. Database migrations run automatically
4. No manual intervention required

**Rollback Safety**:
- All database migrations are idempotent
- Can safely rollback to previous version if needed
- See DEPLOYMENT.md for rollback procedures

---

## Previous Versions

### [Initial Development] - 2025-2026

- Floor plan management system
- Reservation import from PDF
- Auto-assignment algorithm
- PDF annotation and export
- Menu and allergen management
- Drinks inventory and purchase orders
- Billing and invoicing
