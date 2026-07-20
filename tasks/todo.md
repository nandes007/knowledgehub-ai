# KnowledgeHub AI — Task Index

Master plan: [`../knowledgehub-ai.md`](../knowledgehub-ai.md). One file per task below; each is tracked as its own GitHub issue. Work top-to-bottom; parallel tracks noted.

**Workflow:** branch (name given in each file) → implement → open PR with `Closes #<issue>` in the description → merging to `main` auto-closes the issue.

## Phase 0–1: Foundation + RAG API
- [ ] [00 Repo & tooling setup](00-repo-setup.md) — [#1](https://github.com/nandes007/knowledgehub-ai/issues/1)
- [ ] [01 FastAPI + Postgres skeleton](01-fastapi-postgres-skeleton.md) — [#2](https://github.com/nandes007/knowledgehub-ai/issues/2)
- [ ] [02 RAG chat endpoint (non-streaming)](02-rag-chat-endpoint.md) — [#3](https://github.com/nandes007/knowledgehub-ai/issues/3)
- [ ] [03 SSE streaming](03-sse-streaming.md) — [#4](https://github.com/nandes007/knowledgehub-ai/issues/4)
- [ ] [04 Conversation persistence](04-conversation-persistence.md) — [#5](https://github.com/nandes007/knowledgehub-ai/issues/5)
- [ ] [05 Backend tests → tag v0.1.0](05-backend-tests-v010.md) — [#6](https://github.com/nandes007/knowledgehub-ai/issues/6) ← checkpoint

## Phase 2: Chat UI
- [ ] [06 Chat UI layout (fake data)](06-chat-ui-layout.md) — [#7](https://github.com/nandes007/knowledgehub-ai/issues/7)
- [ ] [07 Wire frontend to backend](07-wire-frontend-backend.md) — [#8](https://github.com/nandes007/knowledgehub-ai/issues/8)
- [x] [08 Streaming UI](08-streaming-ui.md) — [#9](https://github.com/nandes007/knowledgehub-ai/issues/9)
- [x] [09 History UI](09-history-ui.md) — [#10](https://github.com/nandes007/knowledgehub-ai/issues/10)
- [x] [10 UI polish → tag v0.2.0](10-ui-polish-v020.md) — [#11](https://github.com/nandes007/knowledgehub-ai/issues/11) ← checkpoint

## Phase 3: Knowledge upload (11–13 can run parallel to 06–10)
- [x] [11 Upload endpoint](11-upload-endpoint.md) — [#12](https://github.com/nandes007/knowledgehub-ai/issues/12)
- [x] [12 Background ingestion + per-file upsert](12-background-ingestion.md) — [#13](https://github.com/nandes007/knowledgehub-ai/issues/13)
- [x] [13 Document list & delete](13-document-list-delete.md) — [#14](https://github.com/nandes007/knowledgehub-ai/issues/14)
- [x] [14 Knowledge page UI](14-knowledge-page-ui.md) — [#15](https://github.com/nandes007/knowledgehub-ai/issues/15)
- [x] [15 End-to-end loop → tag v0.3.0](15-e2e-loop-v030.md) — [#16](https://github.com/nandes007/knowledgehub-ai/issues/16) ← checkpoint

## Phase 4: Auth + citations + robustness
- [x] [16 Auth backend](16-auth-backend.md) — [#17](https://github.com/nandes007/knowledgehub-ai/issues/17)
- [x] [17 Auth frontend](17-auth-frontend.md) — [#18](https://github.com/nandes007/knowledgehub-ai/issues/18)
- [x] [18 Citations](18-citations.md) — [#19](https://github.com/nandes007/knowledgehub-ai/issues/19)
- [ ] [19 Ugly inputs → tag v0.4.0](19-ugly-inputs-v040.md) — [#20](https://github.com/nandes007/knowledgehub-ai/issues/20) ← checkpoint

## Phase 5: Production
- [ ] [20 Dockerize](20-dockerize.md) — [#21](https://github.com/nandes007/knowledgehub-ai/issues/21)
- [ ] [21 Deploy](21-deploy.md) — [#22](https://github.com/nandes007/knowledgehub-ai/issues/22)
- [ ] [22 Observability](22-observability.md) — [#23](https://github.com/nandes007/knowledgehub-ai/issues/23)
- [ ] [23 Hardening](23-hardening.md) — [#24](https://github.com/nandes007/knowledgehub-ai/issues/24)
- [ ] [24 Portfolio README → tag v1.0.0](24-portfolio-readme-v100.md) — [#25](https://github.com/nandes007/knowledgehub-ai/issues/25) ← MVP 🎉

## Phase 6–7: v2 + evals (pick by energy)
- [ ] [25 Department visibility](25-v2-department-visibility.md) — [#26](https://github.com/nandes007/knowledgehub-ai/issues/26)
- [ ] [26 Hybrid search + rerank](26-v2-hybrid-search-rerank.md) — [#27](https://github.com/nandes007/knowledgehub-ai/issues/27)
- [ ] [27 Admin dashboard](27-v2-admin-dashboard.md) — [#28](https://github.com/nandes007/knowledgehub-ai/issues/28)
- [ ] [28 Evals: RAGAS + retrieval metrics](28-evals-ragas.md) — [#29](https://github.com/nandes007/knowledgehub-ai/issues/29)

## Per-task loop
```bash
git checkout -b <branch-from-task-file>
# implement, e.g. /agent-skills:build tasks/01-fastapi-postgres-skeleton.md
git push -u origin <branch-from-task-file>
gh pr create --title "..." --body "Closes #<issue-number>"
# merging the PR auto-closes the linked issue
```
