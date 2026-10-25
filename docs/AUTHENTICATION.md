# Authentication

Protected API routes verify Auth0 access tokens locally. The browser obtains a token with the Auth0 React SDK and sends `Authorization: Bearer <access_token>`. FastAPI checks the signature against the tenant JWKS, then checks the issuer, audience, expiration, `nbf` when present, and a nonempty `sub`. The accepted algorithm is RS256. `alg: none`, other algorithms, expired tokens, and ID tokens whose audience is the SPA client are rejected.

The official `auth0-fastapi-api` package is still a beta (`1.0.0b9` as of this change), so the API uses PyJWT and the `cryptography` extra instead.

## Dashboard setup

Create these values in the Auth0 Dashboard. This repository does not contain an API identifier, and none is invented here.

1. Applications → APIs → Create API.
2. Set the signing algorithm to RS256.
3. Copy the API identifier into `AUTH0_AUDIENCE` and `VITE_AUTH0_AUDIENCE`. Do not use the SPA client ID as the audience.
4. In the existing SPA application, allow the frontend origin for callback, logout, and web origins. Local development uses `http://localhost:5173`.
5. Authorize that SPA to request tokens for the API.
6. Set `AUTH0_DOMAIN` to the tenant host with no scheme. The SPA already registered in this project uses `dev-cavt8qsoguvw8bjv.us.auth0.com`.
7. Leave `AUTH0_ISSUER` empty unless the issuer differs from `https://AUTH0_DOMAIN/`.

No client secret belongs in the SPA or in `backend/.env`. The API downloads public signing keys only. Missing domain or audience makes every protected route return `503` with `Authentication is not configured.` Demo mode does not skip this check.

## Request behavior

| Situation | Status |
| --- | --- |
| Missing or invalid access token | 401 |
| Valid token without the optional `AUTH0_REQUIRED_SCOPE` | 403 |
| Auth0 settings missing, TigerData disconnected, or migration 004 not applied | 503 |
| Process-local account limit reached | 429 |

`GET /api/v1/health` stays public. `GET /api/v1/health/database` and `GET /api/v1/dev/dataset-test` do not. The dataset route also stays hidden unless `DEV_ROUTES_ENABLED=true`.

The cached research example in the browser does not call these routes. Logging out leaves that preview usable. Login is only started from the Log in and Sign up buttons.

## Ownership

The verified `sub` is the only owner. Request fields named `user_sub`, `user_id`, or `owner_id` are not authorization. Discovery persistence receives that subject as a value, then opens its own database connection. It does not insert an anonymous history row. Reads filter `research_queries.user_sub`. A query id that is missing or owned by someone else returns `404`.

## Limits

Discovery, analysis, exploration, and similarity limits are enforced after authentication and before Gemini, embedding search, or dataset download. Each worker keeps its own counters. Restarting the process clears them. They are not shared across workers and they are not a Redis quota.

## Tests

Ordinary tests sign tokens with a local RSA key and install that key as the JWKS source. They do not call Auth0, Gemini, or TigerData. Applying migration 004 to the shared database is a separate manual step described in `docs/DATABASE.md`.
