Check the key exists, then push it:

ls ~/.ssh/id_ed25519.pub || ssh-keygen -t ed25519
ssh-copy-id -i ~/.ssh/id_ed25519.pub root@IPSERVER   # prompts for the root password
ssh root@IPSERVER 'hostname'                          # must succeed with no prompt

Then re-run the playbook unchanged.

Three things that could bite depending on what you find:

If ssh-copy-id itself is denied — the provider disabled root password login. Add your key through the VirtualLabs console/VNC, or use whatever user they gave you and run ansible-playbook -i inventory.yml site.yml --ask-vault-pass -e bootstrap_user=<thatuser>.

If you generated a new key just now, inventory.yml already points at ~/.ssh/id_ed25519.pub, so nothing to change. If your existing key is a different name (id_rsa, work key, etc.), update ssh_pubkey_file — that's the key the playbook installs for nandes, and getting it wrong locks you out of every re-run.

If ssh hangs instead of denying, that's IPv6 reachability, not auth — bring up WARP.

I'd skip --ask-pass; it needs sshpass, which is deliberately painful to install on macOS.


cd deploy
mv vault.yml.example vault.yml          # real secrets belong here
ansible-vault encrypt vault.yml
git checkout deploy/vault.yml.example 2>/dev/null || true   # restore placeholder template


I checked both servers instead of guessing, and found the thing that would have made this fail silently.

What's true now: both servers are in the same IPv6 /64, and …::1c4 already reaches …::1bb over TCP. So no tunnel — the app connects straight to the database's IPv6 address. I ripped the reverse-tunnel machinery out; it was built on the IPv4-only premise.

What I changed in the knowledgehub ansible:
- pg_client_hosts in inventory.yml — set to 2407:6ac0:3:9d:abcd::1c4/128. That drives three things: listen_addresses gains the host's own address, pg_hba.conf gets a hostssl … scram-sha-256 line for that /128, and ufw opens 5432 from that address only.
- meeting_room_booking database + schema, owned by nandestech (Hibernate's default_schema and Liquibase both need the schema to exist; neither creates it).
- ssl = on explicitly.

The catch — your api container can't reach IPv6. Verified on …::1c4:
podman network inspect meeting-room-booking_default → ipv6_enabled=false, subnet 10.89.1.0/24
Rootless podman's bridge is IPv4-only. The host reaches the database fine; the container has no route to any IPv6 address. It works with Supabase today only because that pooler is IPv4. Open the firewall and the app would still fail with "Network is unreachable" — the same trap that made knowledgehub's compose use network_mode: host.

So meeting-room-booking needs the same fix — three edits:

# docker-compose.prod.yml
  api:
    network_mode: host          # + this
    environment:
      - SERVER_ADDRESS=127.0.0.1   # + this, so 8080 isn't exposed publicly
  frontend:
    network_mode: host          # + this
    # ports: - "9100:80"        # - remove, nginx binds the host directly
# meeting-room-booking-fe/nginx.conf
listen 9100;                        # was 80 — host nginx already proxies to 9100
proxy_pass http://127.0.0.1:8080/;  # was http://api:8080/ — no compose network now

Then .env on that server:
env
DB_URL=jdbc:postgresql://[2407:6ac0:3:9d:abcd::1bb]:5432/meeting_room_booking?sslmode=require
DB_USER=nandestech
DB_PASSWORD=<postgres_password from the vault>
Brackets around the IPv6 address are required in a JDBC URL. Liquibase then creates its tables in the meeting_room_booking schema on startup.

Order to run things:
cd deploy/ansible
ansible-playbook -i inventory.yml postgres.yml --ask-vault-pass   # db, schema, hba, ufw
# then on ...::1c4: edit .env, rebuild fe (nginx.conf is baked in), restart

Verified: syntax checks pass, listen_addresses renders as localhost,2407:6ac0:3:9d:abcd::1bb, and the summary prints the exact JDBC URL. Not verified end-to-end — the firewall rule doesn't exist until you run the playbook.

Want me to make those three edits in meeting-room-booking? They're in a separate repo, so I left it untouched.