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