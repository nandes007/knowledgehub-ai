# Production Deployment: knowledgehubai.nandes.tech

**Merges:** #22 (Deploy to Public URL) · #23 (Observability) · #24 (Hardening)
**Branch:** `chore/deploy-production`
**Goal:** KnowledgeHub AI running production-ready at `https://knowledgehubai.nandes.tech`, deployed automatically from `main` via GitHub Actions.

---

## Target Architecture

```
User (IPv4/IPv6)
   │
Cloudflare (proxied DNS, TLS, IPv4→IPv6 bridge)
   │
8labs.id VPS (IPv6-only, 4 vCPU / 8GB / 33GB, Ubuntu, root)
   │
Caddy (reverse proxy, origin TLS, SSE pass-through)
   ├── frontend  (Next.js, :3000 internal)
   └── backend   (FastAPI, :8000 internal)
        └── Postgres + Chroma + uploads (Podman volumes)

GitHub Actions ──(SSH over Cloudflare Tunnel)──> VPS
```

Key constraint: the VPS is **IPv6-only**. Two consequences drive the design:

1. **Visitors** — Cloudflare proxied (orange-cloud) `AAAA` record makes the site reachable from IPv4 clients; Cloudflare talks to the origin over IPv6.
2. **GitHub Actions runners have no IPv6** — deploy SSH goes through a Cloudflare Tunnel (`cloudflared`), same approach as my previous deployment.

---

## Phase 1 — Server Preparation

- [ ] SSH into VPS (root via public IPv6), update OS
- [ ] Install Podman + `podman-compose`
- [ ] Install and authenticate `cloudflared`; create tunnel with an SSH ingress route (e.g. `ssh.knowledgehubai.nandes.tech`)
- [ ] Create a non-root `deploy` user for CI (SSH key auth only), running **rootless Podman**:
  - `loginctl enable-linger deploy` so containers survive logout/reboot
  - `sysctl net.ipv4.ip_unprivileged_port_start=80` so rootless Caddy can bind 80/443
- [ ] Enable `podman-restart.service` (or systemd Quadlet units later) — Podman has no daemon, so `restart: unless-stopped` alone won't bring containers back after reboot
- [ ] Firewall (ufw/nftables): allow 80/443 + SSH; everything else closed

## Phase 2 — DNS & TLS

- [ ] Cloudflare DNS: `AAAA knowledgehubai` → VPS IPv6, **proxied**
- [ ] Tunnel hostname for CI SSH access
- [ ] Cloudflare SSL mode **Full (strict)**; Caddy holds the origin certificate
- [ ] Verify: site loads over HTTPS from an IPv4-only network (e.g. phone on mobile data)

## Phase 3 — Production Compose Stack

- [ ] Add `docker-compose.prod.yml`:
  - Adds `caddy` service (ports 80/443, `Caddyfile` mounted, cert volume)
  - Backend/frontend/Postgres: **no host port mappings** — internal network only
  - Backend/frontend images pulled from GHCR (not built on the server) — OCI images, so Podman pulls them fine
  - `restart: unless-stopped` everywhere (works with `podman-restart.service` from Phase 1)
  - Fully-qualified image names (`docker.io/...`, `ghcr.io/...`) — Podman doesn't default to Docker Hub; the existing compose file already does this
- [ ] Add `Caddyfile`: route `/api/*` → backend, everything else → frontend; **disable response buffering for the SSE chat route**
- [ ] Create `.env` on the server by hand (API keys, DB password, CORS origin) — never committed
- [ ] Verify: full demo loop (login → upload → chat with streaming) works from a phone

## Phase 4 — CI/CD (GitHub Actions)

- [ ] Workflow `deploy.yml` on push to `main`:
  1. Run backend + frontend tests
  2. Build both images, push to GHCR tagged with commit SHA + `latest`
  3. SSH to VPS through `cloudflared` tunnel (as `deploy` user)
  4. `podman-compose -f docker-compose.prod.yml pull && podman-compose -f docker-compose.prod.yml up -d`
  5. Wait for `/healthz`; fail the job loudly if unhealthy
- [ ] Server-side `podman login ghcr.io` once (read-only PAT) so pulls of private images work
- [ ] GitHub repo secrets: `SSH_PRIVATE_KEY`, `SSH_HOST` (tunnel hostname), plus GHCR uses the built-in `GITHUB_TOKEN`
- [ ] Rollback = re-run the workflow from the previous green commit (SHA-tagged images make this trivial)

## Phase 5 — Observability (#23)

- [ ] Structured JSON logging with request context (request id, user, path)
- [ ] Log every LLM call: model, prompt tokens, completion tokens
- [ ] `GET /admin/stats`: messages/day, document count, estimated cost — admin-only
- [ ] `podman logs` / journald is the log sink for now (no external stack)
- [ ] Verify: can answer "what did yesterday cost?" from the endpoint/logs

## Phase 6 — Hardening (#24)

- [ ] Rate limiting (`slowapi`) on `/chat` and `/documents` per user/IP
- [ ] Message length + upload file size limits enforced server-side
- [ ] Strict CORS: only `https://knowledgehubai.nandes.tech`
- [ ] Security headers (Caddy): HSTS, nosniff, frame-deny, referrer-policy
- [ ] Nightly `pg_dump` cron to a local backups dir (33GB disk — keep last 7, prune)
- [ ] Verify: hammering `/chat` returns 429s, not a huge OpenAI bill

## Phase 7 — Go-Live Checklist

- [ ] All secrets on server/GitHub only; `git grep` confirms none committed
- [ ] SSE streaming confirmed through Cloudflare + Caddy (no buffering, no timeouts on long answers)
- [ ] `docs/architecture.md` updated with deployment topology
- [ ] Tag release `v1.0.0`

---

## Acceptance Criteria (merged from #22 / #23 / #24)

- App reachable at `https://knowledgehubai.nandes.tech` from any network (IPv4 included)
- Push to `main` deploys automatically; failed health check fails the pipeline
- SSE streaming works end-to-end through Cloudflare and Caddy
- JSON logs with request context; every LLM call logged with token counts
- Stats endpoint reports messages/day, doc count, estimated cost
- Rate limits, input limits, strict CORS, security headers in place
- Backup approach documented and running
- No secrets in the repository

## Implementation & Testing Notes

Things that need actual code/config work (buildable via `/agent-skill:build` per phase):

1. **`Caddyfile` SSE config** — the one spot most likely to silently break: Caddy must not buffer the `/api/chat` stream, and Cloudflare must not either (SSE generally passes through Cloudflare proxy fine, but test a long streamed answer explicitly).
2. **`docker-compose.prod.yml`** — current `docker-compose.yml` exposes 5432/8000/3000 on the host; prod file must drop those so only Caddy is public.
3. **GHCR image builds** — frontend bakes `NEXT_PUBLIC_API_URL` at build time (build arg), so the production URL must be set in the Actions build step, not at runtime.
4. **Deploy workflow SSH-over-tunnel step** — reuse the `cloudflared access ssh` pattern from the previous project's workflow.
5. **Rootless Podman quirks to test on the server** — port binding after the sysctl change, container auto-start after a real reboot, and volume permissions (rootless volumes live under the deploy user's home; check the 33GB disk layout).
6. **Observability + hardening** are plain backend tasks — implement after the site is live so verification runs against production.

Manual test after go-live: full loop from a phone on mobile data (IPv4) — register, upload a document, ask a question, watch it stream, check citations.
