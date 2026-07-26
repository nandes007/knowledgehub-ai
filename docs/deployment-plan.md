# Deployment Plan — knowledgehubai.nandes.tech

Target: VirtualLabs Large (4 vCPU / 8 GB RAM / 33 GB disk, **public IPv6 only**), Ubuntu-style host,
rootless **Podman** as user `nandes`, **Supabase** as the Postgres, **Cloudflare** for DNS + TLS edge.

Goal: both frontend and backend live and working at `https://knowledgehubai.nandes.tech`.

---

## 0. Architecture

```
Browser (IPv4 or IPv6)
        |
        v
Cloudflare (proxied, terminates public TLS)   <-- gives IPv4 visitors access to an IPv6-only origin
        |  AAAA -> server public IPv6, port 443
        v
host nginx (Cloudflare Origin cert)
        |                          |
   /  -> 127.0.0.1:3000       /api/ -> 127.0.0.1:8000  (prefix stripped)
        |                          |
   podman: frontend            podman: backend (FastAPI)
   (Next.js standalone)             |         |
                                    |         +-- volume chroma_data  (vector store, on-disk)
                                    |         +-- volume uploads_data (source files)
                                    v
                            Supabase Postgres (over IPv6, sslmode=require)
```

**Single origin, no CORS.** The backend mounts its routes at the root (`/auth`, `/chat`,
`/documents`, `/conversations`, `/healthz`), so nginx maps `location /api/` →
`proxy_pass http://127.0.0.1:8000/` and the trailing slash strips `/api`. The frontend is built with
`NEXT_PUBLIC_API_URL=https://knowledgehubai.nandes.tech/api`. One hostname, one certificate, no
preflight requests, no second subdomain.

**Only one backend replica, ever.** Chroma runs in-process against a local persist dir; two
containers writing the same volume would corrupt it. Scale vertically, not horizontally.

---

## 1. Pre-flight — decisions and things to have ready

| Item | Value / where to get it |
|---|---|
| Server public IPv6 | VirtualLabs panel |
| Domain | `knowledgehubai.nandes.tech` (Cloudflare-managed) |
| Supabase project | Create at supabase.com, note the **direct connection** string |
| OpenAI API key | Existing `OPENAI_API_KEY` |
| New `JWT_SECRET` | `openssl rand -hex 32` — do **not** reuse the dev value |
| Your workstation | Needs IPv6 to SSH. No IPv6 at home → install **Cloudflare WARP** first and verify `curl -6 https://ifconfig.co` works |

⚠️ **The single biggest risk in this deployment is the IPv6-only network.** Phase 3 exists purely to
de-risk it, and it should be done *before* anything else is installed. Read it now.

---

## Automated route — Ansible from your laptop

`deploy/ansible/site.yml` implements Phases 1, 3, 4, 6, 7, 8 and 9. The phases below remain the
reference (and the manual fallback); run either.

```bash
cd deploy/ansible
$EDITOR inventory.yml                      # server IPv6 address
cp vault.yml.example vault.yml && $EDITOR vault.yml
ansible-vault encrypt vault.yml
# Cloudflare -> SSL/TLS -> Origin Server -> Create Certificate
#   save the two PEM blocks as certs/origin.pem and certs/origin.key
ansible-playbook -i inventory.yml site.yml --ask-vault-pass
```

**Still done by hand** — one-time dashboard work, not worth automating:

- Phase 2, Cloudflare DNS (AAAA, proxied) and SSL mode Full (strict)
- Phase 8.1, creating the Origin certificate (the playbook installs it, and asserts loudly if
  `deploy/ansible/certs/` is empty)
- Phase 5, creating the Supabase project
- Phase 10, the end-to-end verification clicks

**Two things about the playbook worth knowing before you run it:**

1. It deploys **committed `HEAD`**, via `git archive` — not your working tree. Uncommitted changes are
   silently not deployed. This is deliberate: it removes any need for a deploy key or PAT on an
   IPv6-only server for a private repo.
2. The first play connects as `root` and ends by disabling root SSH. Re-runs therefore need
   `-e bootstrap_user=nandes`, which the playbook header documents.

Both plays are idempotent apart from the image build, which always runs. `--tags bootstrap` does
server setup only; `--skip-tags bootstrap` does an app-only redeploy.

---

## Phase 1 — First contact and the `nandes` user

From your workstation (with IPv6 / WARP up):

```bash
ssh root@<SERVER_IPV6>          # e.g. ssh root@2401:xxxx:...:1
```

- [ ] **1.1** Update the base system

  ```bash
  apt update && apt upgrade -y
  ```

- [ ] **1.2** Create the deploy user

  ```bash
  adduser --gecos "" nandes
  usermod -aG sudo nandes
  ```

- [ ] **1.3** Give it your SSH key (run *on the server*, pasting your public key)

  ```bash
  install -d -m 700 -o nandes -g nandes /home/nandes/.ssh
  echo 'ssh-ed25519 AAAA... you@laptop' > /home/nandes/.ssh/authorized_keys
  chown nandes:nandes /home/nandes/.ssh/authorized_keys
  chmod 600 /home/nandes/.ssh/authorized_keys
  ```

- [ ] **1.4** Verify from a **second terminal** before you lock anything down

  ```bash
  ssh nandes@<SERVER_IPV6> 'id && sudo -n true || echo "sudo needs password (fine)"'
  ```

- [ ] **1.5** Harden SSH — `/etc/ssh/sshd_config`: `PermitRootLogin no`, `PasswordAuthentication no`,
      then `systemctl restart ssh`. **Keep the root session open** until you've re-confirmed the
      `nandes` login works.

- [ ] **1.6** Firewall (IPv6 rules included by default in ufw)

  ```bash
  ufw allow OpenSSH
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw enable
  ufw status verbose        # confirm IPv6 is "on"
  ```

- [ ] **1.7** Optional but cheap insurance on 8 GB with a Next.js build: 2 GB of swap

  ```bash
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  ```

**Done when:** you can `ssh nandes@<SERVER_IPV6>`, root login is refused, ufw is active.

---

## Phase 2 — Cloudflare DNS (do it early, propagation takes time)

In the Cloudflare dashboard for `nandes.tech`:

- [ ] **2.1** DNS → Add record: **AAAA**, name `knowledgehubai`, content `<SERVER_IPV6>`,
      **Proxy status: Proxied (orange cloud)**.
      *The orange cloud is not optional here — it's what lets IPv4-only visitors reach an
      IPv6-only origin.*
- [ ] **2.2** Do **not** add an A record. There is no IPv4 origin.
- [ ] **2.3** SSL/TLS → Overview → mode **Full (strict)**. (Set it now; the origin cert arrives in
      Phase 7. Expect 5xx from the edge until nginx is up — that's expected, not a failure.)
- [ ] **2.4** SSL/TLS → Edge Certificates → **Always Use HTTPS: On**.

**Done when:** `dig AAAA knowledgehubai.nandes.tech` returns Cloudflare addresses (not your server's
— that's the proxy working correctly).

---

## Phase 3 — Prove outbound connectivity (the IPv6-only trap)

An IPv6-only host cannot reach IPv4-only services. Several things this build needs are
IPv4-only or partially so — most notoriously **Docker Hub** (`registry-1.docker.io`), which serves
the `python:3.12-slim` and `node:22-alpine` base images. Find out now, not during the first build.

- [ ] **3.1** As `nandes`, check what you actually have:

  ```bash
  ip -6 addr show; ip -4 addr show          # is there any public IPv4 at all?
  curl -s6 https://ifconfig.co || echo "NO IPv6 EGRESS"
  curl -s4 --max-time 8 https://ifconfig.co || echo "NO IPv4 EGRESS"
  ```

- [ ] **3.2** Test each host the deployment depends on:

  ```bash
  for h in registry-1.docker.io auth.docker.io pypi.org files.pythonhosted.org \
           registry.npmjs.org api.openai.com github.com; do
    printf '%-28s AAAA:%s  reachable:%s\n' "$h" \
      "$(dig +short AAAA $h | head -1 | grep -q . && echo yes || echo NO)" \
      "$(curl -sI --max-time 8 https://$h >/dev/null 2>&1 && echo yes || echo NO)"
  done
  ```

- [ ] **3.3** **If anything shows `NO`** (Docker Hub almost certainly will), enable **NAT64/DNS64** —
      one resolver change makes IPv4-only hosts reachable from an IPv6-only box:

  ```bash
  sudo mkdir -p /etc/systemd/resolved.conf.d
  sudo tee /etc/systemd/resolved.conf.d/dns64.conf >/dev/null <<'EOF'
  [Resolve]
  DNS=2001:4860:4860::6464 2001:4860:4860::64
  Domains=~.
  EOF
  sudo systemctl restart systemd-resolved
  ```

  Re-run 3.2 — every host should now be reachable. Podman containers inherit the host resolver, so
  this covers builds and runtime both.

  *Alternative if DNS64 is unavailable:* install Cloudflare WARP on the server for IPv4 egress. Try
  DNS64 first — it's a config file, not a daemon.

- [ ] **3.4** Confirm the Supabase host resolves (Supabase's **direct** connection endpoint is
      IPv6-native, which suits this server perfectly):

  ```bash
  dig +short AAAA db.<PROJECT_REF>.supabase.co
  ```

**Done when:** every host in 3.2 reports `reachable:yes`. **Do not proceed otherwise** — every later
phase will fail in a confusing way.

---

## Phase 4 — Podman

- [ ] **4.1** Install

  ```bash
  sudo apt install -y podman podman-compose uidmap slirp4netns fuse-overlayfs git nginx
  ```

- [ ] **4.2** Rootless smoke test as `nandes` (this is also a second connectivity check):

  ```bash
  podman run --rm docker.io/library/alpine:3 echo podman-ok
  ```

- [ ] **4.3** Allow the containers to keep running when you log out:

  ```bash
  sudo loginctl enable-linger nandes
  ```

  Without lingering, systemd tears down the user session — and every container in it — the moment
  your SSH session ends.

**Done when:** `podman run` prints `podman-ok` and `loginctl show-user nandes | grep Linger` says
`yes`.

---

## Phase 5 — Supabase

- [ ] **5.1** Create the project; region closest to the server.
- [ ] **5.2** Project Settings → Database → copy the **direct connection** URI
      (`db.<ref>.supabase.co:5432`), *not* the pooler — the pooler is IPv4-only and would force you
      back through NAT64 for every query.
- [ ] **5.3** Rewrite it for this app's driver and add TLS:

  ```
  postgresql+psycopg://postgres:<PASSWORD>@db.<REF>.supabase.co:5432/postgres?sslmode=require
  ```

  Note the `+psycopg` — SQLModel/SQLAlchemy needs the driver named explicitly. URL-encode any
  special characters in the password.

- [ ] **5.4** Schema: the app calls `SQLModel.metadata.create_all()` on startup, so tables are
      created automatically on first boot. There are no migrations — a future schema change means
      hand-written SQL against Supabase.

**Done when:** you have a `DATABASE_URL` string ready. It gets tested for real in Phase 6.

---

## Phase 6 — Code and configuration on the server

As `nandes`, in `/home/nandes`:

- [ ] **6.1** Clone

  ```bash
  git clone https://github.com/<you>/knowledgehub-ai.git
  cd knowledgehub-ai
  ```

- [ ] **6.2** Write `.env` (it is gitignored — it must be created here by hand). Values that differ
      from dev are marked:

  ```bash
  cat > .env <<'EOF'
  # --- Database (Supabase direct connection) ---        # CHANGED
  DATABASE_URL=postgresql+psycopg://postgres:<PASSWORD>@db.<REF>.supabase.co:5432/postgres?sslmode=require

  # --- Storage (compose overrides these to container paths; kept for parity) ---
  CHROMA_PERSIST_DIR=/data/chroma
  UPLOAD_DIR=/data/uploads
  MAX_UPLOAD_SIZE_MB=25

  # --- LLM ---
  LLM_PROVIDER=openai
  OPENAI_API_KEY=<your key>
  EMBEDDING_MODEL=text-embedding-3-small
  CHAT_MODEL=gpt-4o-mini

  # --- Auth ---
  JWT_SECRET=<openssl rand -hex 32>                       # CHANGED - fresh secret
  JWT_ALGORITHM=HS256
  JWT_EXPIRE_MINUTES=1440

  # --- CORS ---
  CORS_ORIGINS=https://knowledgehubai.nandes.tech         # CHANGED

  # --- Frontend (baked into the JS bundle at build time) ---
  NEXT_PUBLIC_API_URL=https://knowledgehubai.nandes.tech/api   # CHANGED
  EOF
  chmod 600 .env
  ```

  `EMBEDDING_MODEL` must match whatever was used to build any existing Chroma data. Fresh server,
  fresh vector store, so anything consistent is fine — just never change it after documents are
  ingested.

- [ ] **6.3** Sanity-check the DB string before burning a full build on it:

  ```bash
  podman run --rm docker.io/library/postgres:16 \
    psql "postgresql://postgres:<PASSWORD>@db.<REF>.supabase.co:5432/postgres?sslmode=require" -c 'select 1'
  ```

  (Plain `postgresql://` here — `psql` doesn't understand the `+psycopg` suffix.)

**Done when:** `select 1` returns from Supabase.

---

## Phase 7 — Build and run the containers

- [ ] **7.1** Build. First run pulls base images and compiles the Next.js app; budget 5–15 minutes.

  ```bash
  cd /home/nandes/knowledgehub-ai
  podman-compose -f docker-compose.prod.yml build
  ```

- [ ] **7.2** Start

  ```bash
  podman-compose -f docker-compose.prod.yml up -d
  podman ps
  ```

- [ ] **7.3** Verify locally, before nginx is in the picture:

  ```bash
  curl -s localhost:8000/healthz        # -> {"status":"ok"}
  curl -sI localhost:3000 | head -1     # -> HTTP/1.1 200 OK
  podman logs knowledgehub-ai_backend_1 --tail 50
  ```

  Both ports are bound to `127.0.0.1` only — nginx is the sole public edge.

- [ ] **7.4** Confirm table creation actually happened (backend logs are clean, and Supabase's Table
      Editor shows `user`, `document`, `conversation`, `message`).

**Done when:** `/healthz` returns ok and the frontend answers 200 on localhost.

**If the build dies on memory:** build the services one at a time
(`podman-compose -f docker-compose.prod.yml build backend`, then `frontend`).

---

## Phase 8 — nginx + Cloudflare Origin certificate

- [ ] **8.1** In Cloudflare: SSL/TLS → Origin Server → **Create Certificate** → hostnames
      `knowledgehubai.nandes.tech`, 15-year validity. Copy both PEM blocks.

  *Why an Origin cert instead of Let's Encrypt:* no ACME challenge to route through the Cloudflare
  proxy, no renewal cron, no IPv6-only validation edge cases. One file, valid for 15 years.

- [ ] **8.2** Install them on the server:

  ```bash
  sudo install -d -m 700 /etc/ssl/cloudflare
  sudo nano /etc/ssl/cloudflare/knowledgehubai.pem   # paste the certificate
  sudo nano /etc/ssl/cloudflare/knowledgehubai.key   # paste the private key
  sudo chmod 600 /etc/ssl/cloudflare/*
  ```

- [ ] **8.3** `sudo nano /etc/nginx/sites-available/knowledgehubai`:

  ```nginx
  server {
      listen 80;
      listen [::]:80;
      server_name knowledgehubai.nandes.tech;
      return 301 https://$host$request_uri;
  }

  server {
      listen 443 ssl;
      listen [::]:443 ssl;
      http2 on;
      server_name knowledgehubai.nandes.tech;

      ssl_certificate     /etc/ssl/cloudflare/knowledgehubai.pem;
      ssl_certificate_key /etc/ssl/cloudflare/knowledgehubai.key;

      # Must be >= MAX_UPLOAD_SIZE_MB, or nginx 413s before the app can answer.
      client_max_body_size 25m;

      # Backend. Trailing slash on proxy_pass strips the /api prefix:
      # /api/auth/login -> /auth/login
      location /api/ {
          proxy_pass http://127.0.0.1:8000/;
          proxy_set_header Host              $host;
          proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto https;

          # /chat is a Server-Sent Events stream. Without these, nginx buffers
          # the whole response and tokens arrive in one lump at the end.
          proxy_buffering off;
          proxy_cache off;
          proxy_read_timeout 300s;
      }

      location / {
          proxy_pass http://127.0.0.1:3000;
          proxy_http_version 1.1;
          proxy_set_header Host              $host;
          proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto https;
          proxy_set_header Upgrade           $http_upgrade;
          proxy_set_header Connection        "upgrade";
      }
  }
  ```

- [ ] **8.4** Enable and reload

  ```bash
  sudo ln -s /etc/nginx/sites-available/knowledgehubai /etc/nginx/sites-enabled/
  sudo rm -f /etc/nginx/sites-enabled/default
  sudo nginx -t && sudo systemctl reload nginx
  ```

**Done when:** `curl -sI https://knowledgehubai.nandes.tech` returns 200 from your workstation.

---

## Phase 9 — Survive a reboot

`restart: unless-stopped` only re-starts a crashed container; it does not bring the stack up after a
host reboot. One systemd **user** unit handles that:

- [ ] **9.1** As `nandes`, `mkdir -p ~/.config/systemd/user` and write
      `~/.config/systemd/user/knowledgehub.service`:

  ```ini
  [Unit]
  Description=KnowledgeHub AI
  After=network-online.target

  [Service]
  Type=oneshot
  RemainAfterExit=yes
  WorkingDirectory=/home/nandes/knowledgehub-ai
  ExecStart=/usr/bin/podman-compose -f docker-compose.prod.yml up -d
  ExecStop=/usr/bin/podman-compose -f docker-compose.prod.yml down
  TimeoutStartSec=0

  [Install]
  WantedBy=default.target
  ```

- [ ] **9.2** Enable

  ```bash
  systemctl --user daemon-reload
  systemctl --user enable --now knowledgehub.service
  ```

- [ ] **9.3** **Actually reboot and re-verify.** An untested restart path is not a restart path.

  ```bash
  sudo reboot
  # ... wait, reconnect ...
  curl -sI https://knowledgehubai.nandes.tech
  curl -s https://knowledgehubai.nandes.tech/api/healthz
  ```

**Done when:** the site is up after a cold boot with nobody logged in.

---

## Phase 10 — End-to-end verification

Through the real domain, in a browser:

- [ ] Register a new account → returns a token, lands in the app
- [ ] Log out, log back in
- [ ] Upload a PDF and a DOCX → status reaches processed
- [ ] Ask a question about the uploaded document → **tokens stream in progressively** (if the answer
      appears all at once, `proxy_buffering off` isn't taking effect)
- [ ] Sources are listed with the answer
- [ ] Ask something unrelated to the corpus → the assistant declines (grounded-only behaviour is by
      design)
- [ ] Reload the page → conversation history persists (proves Supabase writes)
- [ ] Delete a document
- [ ] Upload a file over 25 MB → a clean error, not a hung request
- [ ] Check Supabase Table Editor: rows in `user`, `document`, `conversation`, `message`
- [ ] `podman restart knowledgehub-ai_backend_1` → uploaded docs still answerable (proves the Chroma
      volume persists)

---

## Operations

**Logs**

```bash
podman-compose -f docker-compose.prod.yml logs -f backend
sudo tail -f /var/log/nginx/error.log
```

**Redeploy after a code change**

```bash
cd /home/nandes/knowledgehub-ai && git pull
podman-compose -f docker-compose.prod.yml build
podman-compose -f docker-compose.prod.yml up -d
podman image prune -f          # 33 GB disk; stale layers add up fast
```

A change to `NEXT_PUBLIC_API_URL` requires a **frontend rebuild** — it's compiled into the bundle,
not read at runtime.

**Backup** — the volumes hold everything Supabase doesn't (Supabase backs itself up):

```bash
podman volume export knowledgehub-ai_chroma_data  -o ~/backup/chroma-$(date +%F).tar
podman volume export knowledgehub-ai_uploads_data -o ~/backup/uploads-$(date +%F).tar
```

Worth a weekly cron once the app has real content. Restore with `podman volume import`.

**Disk watch** — 33 GB is not much for container images plus a vector store:

```bash
df -h /; podman system df
```

**Rollback**

```bash
git checkout <previous-good-sha>
podman-compose -f docker-compose.prod.yml build && podman-compose -f docker-compose.prod.yml up -d
```

---

## Known gotchas, in the order they'll bite

| Symptom | Cause | Fix |
|---|---|---|
| Image pull hangs/fails | Docker Hub is IPv4-only | Phase 3.3 — DNS64 |
| DB connect times out | Using the Supabase **pooler** (IPv4) | Use the direct `db.<ref>.supabase.co` endpoint |
| Cloudflare 522 | nginx down, or ufw blocking 443 | `systemctl status nginx`, `ufw status` |
| Cloudflare 526 | SSL mode is Full (strict) but the origin cert is missing/mismatched | Re-do Phase 8.1–8.2 |
| Chat answers appear all at once | nginx buffering the SSE stream | `proxy_buffering off` in `location /api/` |
| 413 on upload | `client_max_body_size` < `MAX_UPLOAD_SIZE_MB` | Raise both together |
| Everything dies when SSH closes | Lingering not enabled | `loginctl enable-linger nandes` |
| Cloudflare 524 on chat | >100 s before the first byte | Only if the LLM stalls; tokens start well inside the window normally |
| 401 loops after redeploy | `JWT_SECRET` changed | Expected — existing sessions are invalidated; log in again |

---

## Deliberately not doing this round

- **CI/CD.** Images build on the server (`git pull && build`). Add a pipeline when redeploys get
  frequent enough to be annoying.
- **Migrations (Alembic).** `create_all()` covers a greenfield schema. Add it at the first
  destructive schema change.
- **Monitoring/alerting.** `podman ps` and the Cloudflare dashboard suffice at this size. Add
  Uptime Kuma or a Cloudflare health check when downtime starts costing something.
- **Restricting port 443 to Cloudflare's IP ranges.** A worthwhile hardening step once the site is
  confirmed working — the origin IPv6 is not published anywhere, so it's low-urgency.
- **Log rotation for container logs.** Podman defaults are fine until they aren't; revisit if
  `podman system df` grows.
