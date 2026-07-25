# Deploy checklist

Code/config side (`docker-compose.prod.yml`, `Caddyfile`, `.github/workflows/deploy.yml`)
is done. Everything below is manual — infra access CI/the assistant doesn't have.
Full architecture and rationale: [`deployment-plan.md`](deployment-plan.md).

## 1. Server (once)

- [ ] SSH into the VPS as root, update OS
- [ ] Install Podman + `podman-compose`
- [ ] Install `cloudflared`, authenticate, create a tunnel with an SSH ingress
      route (e.g. `ssh.knowledgehubai.nandes.tech`) — this is `SSH_HOST` below
- [ ] Create a non-root `deploy` user, SSH key auth only, running rootless Podman:
  - `loginctl enable-linger deploy`
  - `sysctl net.ipv4.ip_unprivileged_port_start=80` so rootless Caddy can bind 80/443
- [ ] Enable `podman-restart.service` so containers survive reboot
- [ ] `ufw`/`nftables`: allow 80/443 + SSH, everything else closed
- [ ] As `deploy`: `mkdir -p ~/knowledgehub-ai`, `podman login ghcr.io` with a
      read-only PAT (so `podman-compose pull` can fetch images)
- [ ] Create `~/knowledgehub-ai/.env` by hand — same keys as `.env.example`
      plus `DOMAIN=knowledgehubai.nandes.tech`; never commit this file

## 2. DNS & TLS (once)

- [ ] Cloudflare DNS: `AAAA knowledgehubai` → VPS IPv6, proxied
- [ ] Cloudflare SSL mode: **Full (strict)** — Caddy issues/holds the origin cert
- [ ] Verify HTTPS loads from an IPv4-only network (e.g. phone on mobile data)

## 3. GitHub repo secrets (once)

- [ ] `SSH_PRIVATE_KEY` — private half of the `deploy` user's key
- [ ] `SSH_HOST` — the tunnel hostname from step 1 (e.g. `ssh.knowledgehubai.nandes.tech`)
- [ ] `GITHUB_TOKEN` is automatic; no setup needed for GHCR push

## 4. First deploy

- [ ] Push to `main` — `deploy.yml` runs tests, builds+pushes images, scp's
      `docker-compose.prod.yml` + `Caddyfile` to the server, and runs
      `podman-compose up -d`, then polls `/healthz`
- [ ] From a phone on mobile data: register, upload a document, ask a
      question, watch it stream, check citations

## Notes

- Caddy routes by the backend's actual route prefixes (`/healthz`, `/auth/*`,
  `/chat`, `/conversations*`, `/documents*`) — the backend has no `/api` prefix,
  so this differs from the shorthand `/api/*` in the original plan doc.
- `/chat` is SSE — `Caddyfile` sets `flush_interval -1` on the backend proxy
  so tokens aren't buffered.
- Rollback: re-run the workflow from the last green commit, or SSH in and
  `IMAGE_TAG=<previous sha> podman-compose -f docker-compose.prod.yml up -d`.
- Observability (#23) and hardening (#24) — rate limiting, security headers,
  backups, stats endpoint — are separate `/build` passes, not covered here.
