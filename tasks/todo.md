# KnowledgeHub AI — Task Index

Master plan: [`../knowledgehub-ai.md`](../knowledgehub-ai.md). One file per task below; each becomes one GitHub issue and one `/build tasks/<file>` run. Work top-to-bottom; parallel tracks noted.

## Phase 0–1: Foundation + RAG API
- [ ] [00 Repo & tooling setup](00-repo-setup.md)
- [ ] [01 FastAPI + Postgres skeleton](01-fastapi-postgres-skeleton.md)
- [ ] [02 RAG chat endpoint (non-streaming)](02-rag-chat-endpoint.md)
- [ ] [03 SSE streaming](03-sse-streaming.md)
- [ ] [04 Conversation persistence](04-conversation-persistence.md)
- [ ] [05 Backend tests → tag v0.1.0](05-backend-tests-v010.md) ← checkpoint

## Phase 2: Chat UI
- [ ] [06 Chat UI layout (fake data)](06-chat-ui-layout.md)
- [ ] [07 Wire frontend to backend](07-wire-frontend-backend.md)
- [ ] [08 Streaming UI](08-streaming-ui.md)
- [ ] [09 History UI](09-history-ui.md)
- [ ] [10 UI polish → tag v0.2.0](10-ui-polish-v020.md) ← checkpoint

## Phase 3: Knowledge upload (11–13 can run parallel to 06–10)
- [ ] [11 Upload endpoint](11-upload-endpoint.md)
- [ ] [12 Background ingestion + per-file upsert](12-background-ingestion.md)
- [ ] [13 Document list & delete](13-document-list-delete.md)
- [ ] [14 Knowledge page UI](14-knowledge-page-ui.md)
- [ ] [15 End-to-end loop → tag v0.3.0](15-e2e-loop-v030.md) ← checkpoint

## Phase 4: Auth + citations + robustness
- [ ] [16 Auth backend](16-auth-backend.md)
- [ ] [17 Auth frontend](17-auth-frontend.md)
- [ ] [18 Citations](18-citations.md)
- [ ] [19 Ugly inputs → tag v0.4.0](19-ugly-inputs-v040.md) ← checkpoint

## Phase 5: Production
- [ ] [20 Dockerize](20-dockerize.md)
- [ ] [21 Deploy](21-deploy.md)
- [ ] [22 Observability](22-observability.md)
- [ ] [23 Hardening](23-hardening.md)
- [ ] [24 Portfolio README → tag v1.0.0](24-portfolio-readme-v100.md) ← MVP 🎉

## Phase 6–7: v2 + evals (pick by energy)
- [ ] [25 Department visibility](25-v2-department-visibility.md)
- [ ] [26 Hybrid search + rerank](26-v2-hybrid-search-rerank.md)
- [ ] [27 Admin dashboard](27-v2-admin-dashboard.md)
- [ ] [28 Evals: RAGAS + retrieval metrics](28-evals-ragas.md)

## Pushing to GitHub issues
```bash
for f in tasks/[0-2]*.md; do
  title=$(head -1 "$f" | sed 's/^# //')
  gh issue create --title "$title" --body-file "$f"
done
```
