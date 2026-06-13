# Deployment Notes

Target public endpoint:

```text
https://app.gridwise.nz/optimise
```

The API also supports the US spelling:

```text
https://app.gridwise.nz/optimize
```

## Required Setup

To make `app.gridwise.nz/optimise` reachable externally:

1. Deploy the FastAPI app from this folder to a web host.
2. Configure the deployed service to run:

   ```bash
   uvicorn gridwise_optimizer.api:app --host 0.0.0.0 --port $PORT
   ```

3. Point `app.gridwise.nz` DNS to the host.
4. Ensure HTTPS is enabled for `app.gridwise.nz`.
5. Verify:

   ```text
   GET  https://app.gridwise.nz/health
   POST https://app.gridwise.nz/optimise
   ```

## Hosting Options

Suitable options:

- Render
- Railway
- Fly.io
- AWS App Runner
- Azure Container Apps
- Existing Gridwise infrastructure behind a reverse proxy

## Path Handling

The current API exposes `/optimise` directly. No path rewrite is required if the service is mounted at the root of `app.gridwise.nz`.

If the service is mounted behind another gateway, route:

```text
POST /optimise
```

to the FastAPI app unchanged.

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

