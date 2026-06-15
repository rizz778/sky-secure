# Sky Secure

A conversational Zoho Projects assistant built with a FastAPI backend and a Next.js chat UI.

The backend uses a LangGraph-based multi-agent architecture to route user input between:

- **Query Agent** for read-only operations
- **Action Agent** for write operations, including create/update/delete tasks
- **Router / supervisor** to decide which agent handles each incoming message

The frontend provides a browser-based chat UI and OAuth login flow.

## Architecture Overview

### Backend

The backend is implemented in `backend/` with FastAPI.

- `backend/app/main.py` — FastAPI application and CORS setup
- `backend/app/api/assistant_routes.py` — `POST /assistant/chat` endpoint for chat messages
- `backend/app/auth/routes.py` — Zoho OAuth routes:
  - `GET /auth/login`
  - `GET /auth/callback`
  - `GET /auth/status`
- `backend/app/agents/router.py` — LangGraph router that coordinates state, session memory, and agent selection
- `backend/app/agents/query_agent.py` — read-only operations
- `backend/app/agents/action_agent.py` — write operations with human-in-the-loop confirmation
- `backend/app/memory/session_memory.py` and `backend/app/memory/user_memory.py` — short-term and longer-term session persistence
- `backend/app/tools/zoho_client.py` — Zoho Projects API wrapper
- `backend/app/tools/zoho_agent_tools.py` — tool adapters used by agents

### Frontend

The frontend is implemented in `client/` with Next.js.

- `client/app/page.tsx` — login screen and OAuth redirect
- `client/app/chat/page.tsx` — chat interface with user/bot messages and confirmation flow
- `client/app/api/chat/route.ts` — forwards chat requests to backend `/assistant/chat`

### LangGraph and Multi-Agent Flow

The message flow is:

1. User sends text from the chat UI
2. Frontend posts to `client/app/api/chat/route.ts`
3. The client proxy forwards the message to `backend/app/api/assistant_routes.py`
4. `backend/app/agents/router.py` loads session/user context and chooses the agent
5. `query_agent` handles read-only queries
6. `action_agent` handles write requests and requires explicit confirmation
7. The backend returns the assistant response and state metadata back to the UI

The backend currently supports human-in-the-loop confirmation for actions, where a user must reply `Yes` to proceed.

## Requirements

- Python 3.11+ / 3.12+ recommended
- Node.js 20+ recommended
- Zoho OAuth credentials (Client ID and Client Secret)
- Local development ports: backend on `8000`, frontend on `3000`

## Local Setup

### Backend

1. Create a Python virtual environment and activate it:

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create `backend/.env` with the values below:

```env
ZOHO_REDIRECT_URI=http://localhost:8000/auth/callback
ZOHO_ACCOUNTS_BASE_URL=https://accounts.zoho.com
ZOHO_SCOPES=ZohoProjects.portals.READ,ZohoProjects.projects.READ,ZohoProjects.tasks.READ,ZohoProjects.tasks.CREATE,ZohoProjects.tasks.UPDATE,ZohoProjects.tasks.DELETE
ZOHO_CLIENT_ID=your_zoho_client_id
ZOHO_CLIENT_SECRET=your_zoho_client_secret
MISTRAL_API_KEY=your_mistral_api_key
MISTRAL_MODEL=mistral-small-latest
FRONTEND_URL=http://localhost:3000
```

4. Start the backend server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

1. Install dependencies:

```bash
cd client
npm install
```

2. Create `client/.env` or set `NEXT_PUBLIC_BACKEND_URL` as needed:

```env
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

3. Start the frontend:

```bash
npm run dev
```

4. Open the app at:

```text
http://localhost:3000
```

## OAuth Login Flow

The app uses Zoho OAuth Authorization Code Grant:

- The user clicks the login button in the frontend
- The frontend redirects to `http://localhost:8000/auth/login`
- The backend redirects the user to Zoho authorization
- Zoho returns to `http://localhost:8000/auth/callback`
- The backend exchanges the code for tokens and saves them locally
- The user is redirected to `/chat`

## Supported Chat Features

The assistant is designed to support conversations such as:

- "What projects do I have?"
- "Show tasks for the first one"
- "Create a task called API Integration"
- "Delete task #5"
- "Who has the most tasks this month?"

The backend is structured to separate query and action responsibilities so read-only operations and write actions stay isolated.

## Known Limitations

- Token storage is currently file-based via `backend/.zoho_tokens.json`, not a per-user database.
- User session handling is minimal; the project assumes a single active Zoho token store.
- Long-term memory is stored in files and has limited persistence.
- The frontend does not currently provide full OAuth status handling beyond the login redirect.
- Tool coverage is partial and may require further Zoho API integration for full task utilisation/member reporting.

## Notes

- `backend/requirements.txt` contains the Python dependencies.
- `client/package.json` contains the frontend dependencies.
- The backend exposes health and assistant endpoints via FastAPI.
- The frontend sends all chat messages through a proxy route to the backend.

## File Structure

```text
backend/
  app/
    api/
      assistant_routes.py
    agents/
      router.py
      query_agent.py
      action_agent.py
    auth/
      routes.py
      login.py
    memory/
      session_memory.py
      user_memory.py
    tools/
      zoho_client.py
      zoho_agent_tools.py
  requirements.txt
client/
  app/
    page.tsx
    chat/page.tsx
    api/chat/route.ts
  package.json
```

## Run Commands

From the root of the repo:

```bash
cd backend
uvicorn app.main:app --reload
```

In another terminal:

```bash
cd client
npm run dev
```

Then open:

```text
http://localhost:3000
```
