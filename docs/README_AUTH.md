# 🔐 VisionGuard AI - Authentication System

## Quick Start

This repository now includes a **complete authentication and authorization system** while maintaining all existing VisionGuard AI functionality.

### 📋 What's New

✅ JWT-based authentication  
✅ Role-based access control (OWNER/MANAGER)  
✅ Shop management with multi-user support  
✅ Protected WebRTC and WebSocket endpoints  
✅ PostgreSQL database with migrations  
✅ Production-ready security

---

## 🚀 Installation & Setup

### 1. Install Dependencies

```powershell
# Install all required packages
pip install -r requirements.txt
```

### 2. Setup PostgreSQL Database

```powershell
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE visionguard_db;

# Exit
\q
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and update:

```powershell
cp .env.example .env
```

Edit `.env`:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/visionguard_db
JWT_SECRET_KEY=your-super-secret-key-change-this
```

### 4. Run Database Migrations

```powershell
# Initialize database schema
alembic upgrade head
```

### 5. Start the Server

```powershell
# Run the application
python main.py
```

Server will start at: **http://localhost:8000**

---

## 📚 Documentation

### For Backend Setup

- **[AUTH_SETUP.md](AUTH_SETUP.md)** - Complete setup guide
  - PostgreSQL configuration
  - Environment variables
  - Database migrations
  - Testing endpoints
  - Troubleshooting

### For Frontend Integration

- **[frontendauth.md](frontendauth.md)** - Complete React/Next.js integration guide
  - Authentication context
  - API client setup
  - Login/Register components
  - Protected routes
  - Shop management
  - WebRTC integration with auth
  - WebSocket integration with auth

### Implementation Details

- **[AUTH_IMPLEMENTATION.md](AUTH_IMPLEMENTATION.md)** - Complete implementation summary
  - All features implemented
  - Files created/modified
  - Security measures
  - Database schema
  - API endpoints

---

## 🔑 Quick Test

### 1. Register an Owner

```powershell
curl -X POST http://localhost:8000/auth/register-owner `
  -H "Content-Type: application/json" `
  -d '{\"name\":\"John Doe\",\"email\":\"john@example.com\",\"password\":\"password123\"}'
```

### 2. Login

```powershell
curl -X POST http://localhost:8000/auth/login `
  -H "Content-Type: application/json" `
  -d '{\"email\":\"john@example.com\",\"password\":\"password123\"}'
```

Copy the `access_token` from the response.

### 3. Create a Shop

```powershell
curl -X POST http://localhost:8000/shops `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" `
  -d '{\"name\":\"Downtown Store\",\"address\":\"123 Main St\",\"assigned_manager_emails\":[\"manager@example.com\"]}'
```

---

## 🌐 API Documentation

Once the server is running, access interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 📁 Project Structure

```
backend-visionguard-ai/
├── main.py                     # Main FastAPI application
├── config.py                   # Configuration settings
├── requirements.txt            # Python dependencies
│
├── # Authentication & Authorization
├── database.py                 # PostgreSQL connection
├── models.py                   # SQLAlchemy models
├── auth_utils.py              # Password & JWT utilities
├── auth_dependencies.py       # Auth middleware
├── auth_routes.py             # Auth endpoints
├── shop_routes.py             # Shop management endpoints
│
├── # Existing VisionGuard AI
├── signaling.py               # WebRTC signaling (now protected)
├── websocket_handler.py       # WebSocket alerts (now protected)
├── session_manager.py         # Session management
├── model_manager.py           # AI model management
├── ai_service.py              # AI processing
│
├── # Database Migrations
├── alembic.ini                # Alembic configuration
├── alembic/
│   ├── env.py                 # Alembic environment
│   ├── script.py.mako         # Migration template
│   └── versions/              # Migration scripts
│
├── # Documentation
├── AUTH_SETUP.md              # Backend setup guide
├── frontendauth.md            # Frontend integration guide
├── AUTH_IMPLEMENTATION.md     # Implementation summary
├── README_AUTH.md             # This file
│
└── # Configuration
    ├── .env.example           # Environment template
    └── .gitignore             # Git ignore rules
```

---

## 🔐 Security Features

### Password Security

- ✅ bcrypt hashing with automatic salt
- ✅ Minimum 8 character requirement
- ✅ Never stored in plain text

### Token Security

- ✅ JWT with HS256 algorithm
- ✅ Access tokens expire in 60 minutes
- ✅ Refresh tokens expire in 7 days
- ✅ Includes user ID, email, and role

### API Security

- ✅ Role-based access control
- ✅ Shop-level permissions
- ✅ Input validation with Pydantic
- ✅ SQL injection prevention
- ✅ CORS configuration
- ✅ HTTPS ready

---

## 👥 User Roles

### OWNER

- Create, update, delete shops
- Assign managers to shops
- Access all owned shops
- View CCTV streams for owned shops

### MANAGER

- View assigned shops only
- Access CCTV streams for assigned shops
- Cannot create or delete shops
- Automatically created when assigned to shop

---

## 🛣️ API Endpoints

### Authentication (`/auth`)

- `POST /auth/register-owner` - Register new owner
- `POST /auth/register-manager` - Register new manager
- `POST /auth/login` - Login user
- `GET /auth/me` - Get current user info
- `POST /auth/logout` - Logout user

### Shops (`/shops`)

- `POST /shops` - Create shop (OWNER only)
- `GET /shops` - List accessible shops
- `GET /shops/{id}` - Get shop details
- `PUT /shops/{id}` - Update shop (OWNER only)
- `DELETE /shops/{id}` - Delete shop (OWNER only)
- `GET /shops/{id}/managers` - List shop managers

### WebRTC & WebSocket (Protected)

- `POST /api/offer` - WebRTC signaling (requires auth & shop access)
- `WS /ws/alerts/{user_id}?token=XXX` - WebSocket alerts (requires auth)

---

## 🔧 Environment Variables

Required in `.env`:

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/visionguard_db

# JWT
JWT_SECRET_KEY=your-secret-key-min-32-chars
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
DEBUG_MODE=True

# CORS
ALLOWED_ORIGINS=http://localhost:3000
```

---

## 🧪 Testing

### Run Tests (Future Enhancement)

```powershell
pytest tests/
```

### Manual Testing

1. Use Swagger UI at http://localhost:8000/docs
2. Click "Authorize" button
3. Enter token: `Bearer YOUR_ACCESS_TOKEN`
4. Test any endpoint

---

## 🐛 Troubleshooting

### Database Connection Failed

```powershell
# Check PostgreSQL is running
Get-Service postgresql*

# Start if needed
Start-Service postgresql-x64-XX
```

### Import Errors

```powershell
# Reinstall dependencies
pip install -r requirements.txt --upgrade
```

### Token Expired

- Tokens expire after 60 minutes
- Login again to get new token
- Implement token refresh in production

---

## 📦 Dependencies

### New Packages Added

- `sqlalchemy` - ORM for database
- `alembic` - Database migrations
- `psycopg2-binary` - PostgreSQL driver
- `pyjwt` - JWT token handling
- `passlib` - Password hashing
- `bcrypt` - Hashing algorithm
- `python-multipart` - Form data support

### Existing Packages

All original VisionGuard AI dependencies remain unchanged.

---

## 🚀 Production Deployment

### Checklist

- [ ] Strong JWT_SECRET_KEY (32+ chars)
- [ ] DATABASE_URL with production credentials
- [ ] DEBUG_MODE=False
- [ ] HTTPS enabled
- [ ] Specific CORS origins (not \*)
- [ ] Database backups configured
- [ ] Environment variables secured
- [ ] Rate limiting enabled
- [ ] Logging configured
- [ ] Monitoring setup

See [AUTH_SETUP.md](AUTH_SETUP.md) for complete production checklist.

---

## 📞 Support

### Resources

- **API Documentation**: http://localhost:8000/docs
- **Setup Guide**: [AUTH_SETUP.md](AUTH_SETUP.md)
- **Frontend Guide**: [frontendauth.md](frontendauth.md)
- **Implementation Details**: [AUTH_IMPLEMENTATION.md](AUTH_IMPLEMENTATION.md)

### Common Issues

- Check logs for error messages
- Verify PostgreSQL is running
- Ensure environment variables are set
- Test endpoints with curl/Postman first

---

## 📝 License

Same as original VisionGuard AI project.

---

## 🎉 Summary

**Your VisionGuard AI now has enterprise-grade authentication!**

✅ Secure user management  
✅ Role-based access control  
✅ Multi-user shop support  
✅ Protected WebRTC/WebSocket  
✅ Production-ready security  
✅ Complete documentation

**Get started in 5 minutes with the Quick Start guide above!** 🚀
