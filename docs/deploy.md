# Deploy checklist

Code/config side (`docker-compose.prod.yml`, `Caddyfile`) is done. Deploys are
manual — no CI workflow. Full architecture and rationale:
[`deployment-plan.md`](deployment-plan.md).

## 1. Server (once)

- [ ] SSH into the VPS as root, update OS
- [ ] Install Podman + `podman-compose`
- [ ] Install `cloudflared`, authenticate, create a tunnel with an SSH ingress
      route (e.g. `ssh.knowledgehubai.nandes.tech`) — use this for your own
      SSH access since the VPS is IPv6-only
- [ ] Create a non-root `deploy` user, SSH key auth only, running rootless Podman:
  - `loginctl enable-linger deploy`
  - `sysctl net.ipv4.ip_unprivileged_port_start=80` so rootless Caddy can bind 80/443
- [ ] Enable `podman-restart.service` so containers survive reboot
- [ ] `ufw`/`nftables`: allow 80/443 + SSH, everything else closed
- [ ] As `deploy`: `mkdir -p ~/knowledgehub-ai`, `podman login ghcr.io` with a
      read-only PAT (so `podman-compose pull` can fetch images)
- [ ] Create `~/knowledgehub-ai/.env` by hand — same keys as `.env.example`
      plus `DOMAIN=knowledgehubai.nandes.tech`; never commit this file
- [ ] `DATABASE_URL` in that `.env` points at Supabase (`postgresql+psycopg://...`),
      not a local container — Postgres isn't run on the VPS, so there's nothing
      to provision or back up here (Supabase handles that)

## 2. DNS & TLS (once)

- [ ] Cloudflare DNS: `AAAA knowledgehubai` → VPS IPv6, proxied
- [ ] Cloudflare SSL mode: **Full (strict)** — Caddy issues/holds the origin cert
- [ ] Verify HTTPS loads from an IPv4-only network (e.g. phone on mobile data)

## 3. Deploy (every release)

From your machine (podman — same commands as Docker, `docker` → `podman`):

```bash
podman login ghcr.io -u <your-github-username>   # once, PAT with write:packages

podman build -t ghcr.io/nandes007/knowledgehub-ai-backend:latest backend
podman build -t ghcr.io/nandes007/knowledgehub-ai-frontend:latest frontend \
  --build-arg NEXT_PUBLIC_API_URL=https://knowledgehubai.nandes.tech
podman push ghcr.io/nandes007/knowledgehub-ai-backend:latest
podman push ghcr.io/nandes007/knowledgehub-ai-frontend:latest

scp docker-compose.prod.yml Caddyfile deploy@ssh.knowledgehubai.nandes.tech:~/knowledgehub-ai/
```

Then on the server (`ssh deploy@ssh.knowledgehubai.nandes.tech`):

```bash
cd ~/knowledgehub-ai
podman-compose -f docker-compose.prod.yml pull
podman-compose -f docker-compose.prod.yml up -d
curl -sf https://knowledgehubai.nandes.tech/healthz
```

- [ ] First deploy done, `/healthz` returns `{"status": "ok"}`
- [ ] From a phone on mobile data: register, upload a document, ask a
      question, watch it stream, check citations

## Notes

- Caddy routes by the backend's actual route prefixes (`/healthz`, `/auth/*`,
  `/chat`, `/conversations*`, `/documents*`) — the backend has no `/api` prefix,
  so this differs from the shorthand `/api/*` in the original plan doc.
- `/chat` is SSE — `Caddyfile` sets `flush_interval -1` on the backend proxy
  so tokens aren't buffered.
- Rollback: build+push the previous commit's images tagged `latest` again
  (or tag by SHA and set `IMAGE_TAG=<sha>` before `podman-compose ... up -d`
  on the server), then re-run the deploy steps above.
- Observability (#23) and hardening (#24) — rate limiting, security headers,
  backups, stats endpoint — are separate `/build` passes, not covered here.
