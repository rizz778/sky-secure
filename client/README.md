# Sky Secure Frontend

Minimal Next.js frontend for the Sky Secure Zoho Projects assistant.

## Setup

1. Install dependencies:
   ```bash
   cd client
   npm install
   ```

2. Run the development server:
   ```bash
   npm run dev
   ```

3. Update `client/.env` if your backend is not running at `http://localhost:8000`.

## Pages

- `/` - Login page that redirects to backend `/auth/login`
- `/chat` - Chat page that sends messages to backend `/assistant/chat`

## Notes

- Uses default `user_id` and `session_id` values: `default-user`, `default-session`
- The frontend proxy simply forwards requests to the backend.
