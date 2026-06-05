# NXT8 — Emergent Google Auth Testing Playbook (saved 2026-06-05)

Saved from `integration_playbook_expert_v2` per Emergent's instructions.

## Variables
- `redirect_url`: derived from `window.location.origin + '/auth/callback'` (NEVER hardcoded)
- `session_id`: one-time token in URL fragment (`#session_id=<id>`)
- `session_token`: persistent (7 days), stored httpOnly cookie + db.user_sessions

## Flow
1. Login button → `https://auth.emergentagent.com/?redirect=<url>`
2. Google OAuth → `<redirect>#session_id=<id>`
3. Frontend extracts session_id, calls `POST /api/auth/session` with header `X-Session-ID`
4. Backend → GET `https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data`
   header `X-Session-ID: <id>`
   returns `{id, email, name, picture, session_token}`
5. Backend: upsert `db.users` (UUID `user_id`), insert `db.user_sessions`
   with 7-day expiry, set httpOnly cookie `session_token`
6. Frontend: redirect to `/dashboard` (or `/home`)

## Auth Resolution (server-side)
- Read `session_token` cookie first, fallback to `Authorization: Bearer ...`
- Lookup `db.user_sessions` → verify expiry → fetch `db.users` by `user_id`
- `_id: 0` projection ALWAYS

## Whitelisted public paths
- `/api/health`
- `/api/payments/webhook`
- `/api/telegram/webhook/{secret}`
- `/api/whatsapp/webhook/{secret}`
- `/api/share/*`
- `/api/s/*`
- `/api/auth/login`, `/api/auth/session`, `/api/auth/logout`

## Testing
- Create test user + session via mongosh
- curl `/api/auth/me` with `Authorization: Bearer <session_token>`
- Playwright: set cookie `session_token` then navigate

## Test identities — see /app/memory/test_credentials.md
