# smart-greenhouse
This is a project based learning for a OOP and design pattern course


## Prerequisites
- Python 3.11+
- Node.js 20 LTS
- Docker Desktop

## Start the stack

1. Copy `.env.example` to `.env`
2. Start Postgres: `docker compose up -d`
3. Backend:
    cd backend python -m venv .venv 
    .venv\Scripts\Activate.ps1 
    pip install -e ".[dev]" 
    alembic upgrade head 
    uvicorn src.main:app --reload

4. Frontend:
    cd frontend 
    npm install 
    npm run dev


- API: http://localhost:8000
- API docs (Scalar): http://localhost:8000/scalar
- Frontend: http://localhost:5173
