# START HERE

If you are opening this project for the first time, read:

- [Getting Started](D:/anker/eufy/docs/GETTING_STARTED.md)

## Fastest path

### Backend

```powershell
cd D:\anker\eufy\backend
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m uvicorn eufy_security_agents.main:app --reload --port 8000
```

Then set this in `backend/.env`:

```dotenv
LLM_API_KEY=your_key_here
```

### Frontend

```powershell
cd D:\anker\eufy\frontend
Copy-Item .env.example .env
npm install
npm run dev
```

## Default local URLs

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
