# Deploy checklist

Same pattern as the roombooking.nandes.tech deploy on this server: host nginx
is the public edge, Cloudflare Flexible in front of it, containers only
reachable on loopback. No Caddy container, no CI, no cloudflared tunnel.
Full architecture and rationale: [`deployment-plan.md`](deployment-plan.md)
(written before this switch — DNS/TLS/proxy sections there are superseded
by this file).

## 0. Confirm you don't need a tunnel

```bash
ssh nandes@<server-ip-or-hostname>
```

If that connects, you're set — skip cloudflared entirely. (It was only ever
needed for GitHub Actions' SSH, which no longer exists now that deploys are
manual.)

## 1. Server (once)

- [ ] Clone/copy the project to the server (same as roombooking)
- [ ] `podman login ghcr.io` with a read-only PAT, so `podman-compose pull` works
- [ ] Create `.env` in the project dir on the server by hand — same keys as
      `.env.example`; never commit this file
- [ ] `DATABASE_URL` in that `.env` points at Supabase
      (`postgresql+psycopg://...`) — Postgres isn't run on this box
- [ ] `podman-compose -f docker-compose.prod.yml up -d` (first run pulls images)

## 2. Host nginx

New server block, same pattern as your other vhosts on this box:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name knowledgehubai.nandes.tech;

    # Backend - exact list of its routes (no /api prefix in this app).
    location = /healthz {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /auth/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /conversations {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /documents {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # SSE - must not be buffered, or tokens arrive all at once at the end.
    location = /chat {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_read_timeout 3600s;
    }

    # Everything else - the Next.js frontend.
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 3600s;
    }
}
```

- [ ] `nginx -t && systemctl reload nginx`

## 3. Cloudflare

- [ ] Add `A` record: `knowledgehubai` → server's public IPv4, proxied (orange cloud)
- [ ] SSL mode: **Flexible** (Cloudflare terminates HTTPS to the visitor, talks
      plain HTTP to nginx — same as roombooking; origin TLS is a later upgrade,
      not blocking)

## 4. Deploy (every release)

From your machine (podman):

```bash
podman login ghcr.io -u <your-github-username>
# Password prompt: paste a PAT (github.com/settings/tokens -> classic ->
# write:packages scope), NOT your GitHub account password - that 403s.

podman build -t ghcr.io/nandes007/knowledgehub-ai-backend:latest backend
podman build -t ghcr.io/nandes007/knowledgehub-ai-frontend:latest frontend \
  --build-arg NEXT_PUBLIC_API_URL=https://knowledgehubai.nandes.tech
podman push ghcr.io/nandes007/knowledgehub-ai-backend:latest
podman push ghcr.io/nandes007/knowledgehub-ai-frontend:latest

scp docker-compose.prod.yml nandes@<server>:~/knowledgehub-ai/
```

Then on the server:

```bash
cd ~/knowledgehub-ai
podman-compose -f docker-compose.prod.yml pull
podman-compose -f docker-compose.prod.yml up -d
curl -sf http://127.0.0.1:8000/healthz
```

- [ ] First deploy done, `/healthz` returns `{"status": "ok"}`
- [ ] `https://knowledgehubai.nandes.tech` loads (Cloudflare + nginx path checks out)
- [ ] From a phone on mobile data: register, upload a document, ask a
      question, watch it stream, check citations

## Notes

- `NEXT_PUBLIC_API_URL` is baked into the frontend image at build time (it's
  read by browser JS), so it must already be the final public URL — same
  domain, no separate API subdomain, so no CORS config needed either.
- Rollback: build+push the previous commit's images tagged `latest` again
  (or tag by SHA and set `IMAGE_TAG=<sha>` before `podman-compose ... up -d`
  on the server), then re-run the deploy steps above.
- Observability (#23) and hardening (#24) — rate limiting, security headers,
  backups, stats endpoint — are separate `/build` passes, not covered here.
