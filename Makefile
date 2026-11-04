ANSIBLE_DIR := deploy/ansible
BOOTSTRAP_USER ?= nandes
# Extra ansible-playbook flags, e.g. make deploy ARGS="--check --diff" or ARGS="--tags env"
ARGS ?=

PLAYBOOK = cd $(ANSIBLE_DIR) && ansible-playbook -i inventory.yml --ask-vault-pass $(ARGS)
VAULT = cd $(ANSIBLE_DIR) && ansible-vault

.DEFAULT_GOAL := help
.PHONY: help deploy deploy-db deploy-qdrant deploy-tailscale vault-edit vault-view vault-encrypt vault-decrypt

help: ## List commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-18s %s\n", $$1, $$2}'

deploy: ## Deploy the app server (site.yml); SSH user via BOOTSTRAP_USER=<user>
	$(PLAYBOOK) site.yml -e bootstrap_user=$(BOOTSTRAP_USER)

deploy-db: ## Provision PostgreSQL: db, schema, hba, ufw (postgres.yml)
	$(PLAYBOOK) postgres.yml

deploy-qdrant: ## Provision Qdrant (qdrant.yml)
	$(PLAYBOOK) qdrant.yml

deploy-tailscale: ## Join servers to the tailnet (tailscale.yml)
	$(PLAYBOOK) tailscale.yml

vault-edit: ## Edit vault.yml in place, stays encrypted
	$(VAULT) edit vault.yml

vault-view: ## Print vault.yml without decrypting the file
	$(VAULT) view vault.yml

vault-encrypt: ## Encrypt vault.yml
	$(VAULT) encrypt vault.yml

vault-decrypt: ## Decrypt vault.yml to plaintext (prefer vault-edit; re-encrypt after)
	$(VAULT) decrypt vault.yml
