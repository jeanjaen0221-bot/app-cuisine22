# Fiche Cuisine Manager

Restaurant management system for Albert Brussels with floor plan management, reservations, and kitchen operations.

## Features

- **Floor Plan Management**: Visual table layout editor with auto-assignment
- **Reservations**: Import from PDF, manage bookings, export annotated PDFs
- **Menu Management**: Track menu items, allergens, and dietary requirements
- **Drinks & Suppliers**: Inventory management and purchase orders
- **Billing**: Invoice generation for reservations

## Tech Stack

### Backend
- **FastAPI** 0.128.0 - Modern Python web framework
- **SQLModel** 0.0.32 - SQL databases with Python type hints
- **PostgreSQL** (production) / SQLite (development)
- **ReportLab** 4.4.9 - PDF generation
- **Uvicorn** 0.40.0 - ASGI server

### Frontend
- **React** 18.3.1 - UI framework
- **TypeScript** 5.6.2 - Type-safe JavaScript
- **Vite** 7.1.12 - Build tool
- **TailwindCSS** 3.4.14 - Utility-first CSS
- **Lucide React** - Icon library

## Getting Started

### Prerequisites
- Python 3.12+
- Node.js 20+
- PostgreSQL (for production) or SQLite (for development)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd applificvhe-cuisine
```

2. **Backend Setup**
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration
```

3. **Frontend Setup**
```bash
cd app/frontend
npm install
```

### Development

**Start Backend** (from project root):
```bash
# Activate virtual environment first
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Run development server
uvicorn app.backend.main:app --reload --host 0.0.0.0 --port 8080
```

**Start Frontend** (from `app/frontend`):
```bash
npm run dev
```

Frontend will be available at `http://localhost:5173`
Backend API at `http://localhost:8080`

### Production Build

**Build Frontend**:
```bash
cd app/frontend
npm run build
```

**Run Production Server**:
```bash
# Set production environment variables
export ENVIRONMENT=production
export DATABASE_URL=postgresql://user:password@host:port/dbname
export ALLOWED_ORIGINS=https://yourdomain.com

# Start server
uvicorn app.backend.main:app --host 0.0.0.0 --port 8080
```

## Scripts

### Backend
```bash
# Run with auto-reload (development)
uvicorn app.backend.main:app --reload

# Run in production mode
uvicorn app.backend.main:app --host 0.0.0.0 --port $PORT
```

### Frontend
```bash
npm run dev          # Development server
npm run build        # Production build
npm run preview      # Preview production build
npm run lint         # Lint code
npm run lint:fix     # Fix linting issues
npm run type-check   # TypeScript type checking
npm run format       # Format code with Prettier
npm run format:check # Check code formatting
```

## Environment Variables

Create a `.env` file in the project root:

```env
# Database (choose one)
DATABASE_URL=sqlite:///./data.db  # Development
# DATABASE_URL=postgresql://user:password@host:port/dbname  # Production

# Server
PORT=8080
ENVIRONMENT=development  # or 'production'

# CORS (production only - comma-separated)
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Optional: Zenchef Integration
# ZENCHEF_API_TOKEN=your_token
# ZENCHEF_RESTAURANT_ID=your_id
```

## Deployment

### Docker

Build and run with Docker:

```bash
docker build -t fiche-cuisine-manager .
docker run -p 8080:8080 -e DATABASE_URL=<your-db-url> fiche-cuisine-manager
```

### Railway / Heroku

The app is configured for Railway/Heroku deployment:

1. Set environment variables in your platform dashboard
2. Push to your deployment branch
3. The `Procfile` and `nixpacks.toml` handle the build process

## API Documentation

When running in development mode, API documentation is available at:
- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`

## Database Migrations

The app uses idempotent migrations that run automatically on startup:
- Column additions
- Index creation
- Constraint management
- Data backfills

For PostgreSQL, additional production migrations handle:
- Duplicate removal
- Unique constraints
- Performance indexes

## Security

- **CORS**: Configurable origins (wildcard in dev, restricted in production)
- **File Uploads**: Size limits and type validation
- **Security Headers**: X-Frame-Options, CSP, HSTS (production)
- **SQL Injection**: Protected via SQLModel/SQLAlchemy
- **XSS**: React auto-escaping + Content Security Policy

## Testing

### Manual Testing Checklist

**Critical Paths**:
- [ ] Create/edit/delete reservations
- [ ] Import PDF reservations
- [ ] Auto-assign tables to reservations
- [ ] Export annotated PDF with table numbers
- [ ] Create/edit floor plan layout
- [ ] Add/remove tables, fixtures, zones
- [ ] Manage menu items and allergens
- [ ] Create purchase orders

**Browser Testing**:
- [ ] Chrome/Edge (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Mobile responsive design

## Troubleshooting

**Backend won't start**:
- Check Python version (3.12+)
- Verify all dependencies installed: `pip install -r requirements.txt`
- Check database connection string
- Review logs for specific errors

**Frontend build fails**:
- Clear node_modules: `rm -rf node_modules && npm install`
- Check Node version (20+)
- Run `npm run type-check` for TypeScript errors

**Database errors**:
- For SQLite: Ensure `data.db` has write permissions
- For PostgreSQL: Verify connection string and credentials
- Check migrations ran successfully (logged on startup)

## License

Proprietary - All rights reserved

## Support

For issues or questions, contact the development team.
