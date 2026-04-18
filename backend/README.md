# AI Automatic Question Generation System - Backend

## Tech Stack
- Python 3.11+
- FastAPI
- SQLAlchemy 2.0
- PostgreSQL
- JWT Authentication

## Quick Start

### 1. Install Dependencies
`ash
pip install -r requirements.txt
`

### 2. Configure Environment
Create a .env file:
`
DATABASE_URL=postgresql://user:password@localhost:5432/exam_db
SECRET_KEY=your-secret-key-change-in-production
`

### 3. Initialize Database
`ash
psql -U postgres -d exam_db -f sql/init.sql
`

### 4. Start Server
`ash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
`

## API Documentation
After starting the server, visit: http://localhost:8000/docs