# Deployment Notes

Target public Gridwise app endpoint:

```text
https://app.gridwise.nz/api/optimise
```

The optimizer service itself exposes:

```text
POST /optimise
POST /optimize
```

## Required Setup

`app.gridwise.nz` is owned by the existing Gridwise Next.js app. Do not point DNS for `app.gridwise.nz` at this optimizer service.

Use this flow:

```text
Client or Ramesh
  -> https://app.gridwise.nz/api/optimise
  -> Gridwise Next.js API route
  -> separate optimizer service /optimise
```

To make this work:

1. Deploy this FastAPI optimizer as a separate service.
2. Configure the optimizer service to run:

   ```bash
   uvicorn gridwise_optimizer.api:app --host 0.0.0.0 --port $PORT
   ```

3. Set `OPTIMISER_API_KEY` on the optimizer service.
4. In the Gridwise Next.js app, add:

   ```text
   OPTIMISER_API_URL=https://<optimizer-service-url>
   OPTIMISER_API_KEY=<same value as optimizer service>
   ```

5. Add a Next.js API route at `web/src/app/api/optimise/route.ts`.
6. That route should forward `POST /api/optimise` to `POST ${OPTIMISER_API_URL}/optimise`.
7. Verify:

   ```text
   GET  https://<optimizer-service-url>/healthz
   POST https://<optimizer-service-url>/optimise
   POST https://app.gridwise.nz/api/optimise
   ```

## Hosting Options

Suitable options:

- Render
- Railway
- Fly.io
- AWS App Runner
- Azure Container Apps
- Google Cloud Run

## Path Handling

The optimizer service exposes `/optimise` directly.

The Gridwise app should expose:

```text
POST /api/optimise
```

and proxy that request to the optimizer service:

```text
POST /optimise
```

No DNS change is required for `app.gridwise.nz`.

## Authentication

The optimizer service supports API-key protection.

Set this environment variable on the optimizer service:

```text
OPTIMISER_API_KEY=<secret>
```

Then callers must send:

```text
x-api-key: <secret>
```

The Gridwise Next.js API route should add this header when forwarding requests. If `OPTIMISER_API_KEY` is not set, the optimizer accepts requests without an API key. That is useful for local development only.

## Runtime Caveat

The current 2-day sample request can take several seconds depending on host CPU and `max_search_states`.

If optimizer calls approach Vercel function timeout limits, avoid a direct synchronous proxy. Use an async job pattern instead:

```text
POST /api/optimise -> creates job
GET  /api/optimise/{jobId} -> polls result
```

## Local Smoke Test

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn gridwise_optimizer.api:app --host 0.0.0.0 --port 8000
```

Then call:

```bash
curl -X POST http://127.0.0.1:8000/optimise \
  -H "Content-Type: application/json" \
  --data-binary @samples/optimizer_request.json
```

With API-key protection enabled:

```bash
OPTIMISER_API_KEY=local-secret \
uvicorn gridwise_optimizer.api:app --host 0.0.0.0 --port 8000

curl -X POST http://127.0.0.1:8000/optimise \
  -H "Content-Type: application/json" \
  -H "x-api-key: local-secret" \
  --data-binary @samples/optimizer_request.json
```
