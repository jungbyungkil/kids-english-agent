Kids English Learning — Azure AI Agent Blueprint

Overview
- Single Learning Agent (tool-calling) with room for Planner/Child Tutor/Parent Concierge split later.
- Azure Functions exposes stateless HTTP tools. Agent selects videos, extracts top words, generates sentences, updates progress, and helps parents.

Key Services
- Azure OpenAI: reasoning, word extraction, example sentences, embeddings.
- Azure AI Search: transcript chunk vector index + filters by CEFR/character tags.
- Azure Video Indexer: transcript extraction (fallback to captions API).
- Azure Speech: TTS cheer; optional STT.
- Azure Maps Search: local academies.
- Cosmos DB: profiles, logs, mastery, level history, academies.
- Storage + CDN: assets, audio, thumbs.
- App Insights: telemetry; Content Safety for guardrails.

Backend
- functions/function_app.py: HTTP routes for all tools with Pydantic validation and stubbed responses.
- openapi.yaml: contract for the tools (used by the agent).
- data/cosmos/schemas.json: collection shapes + index hints.
- infra/bicep/main.bicep: baseline resources (OpenAI, Search, Cosmos, Storage, Functions, App Insights).

Agent Orchestration
- Current streamlit MVP uses Chat Completions + tools in app/tools.py.
- To upgrade: point the agent to call Azure Functions tool endpoints defined here, or use Azure AI Agent Service to register function tools with these schemas.

Next Steps
- Wire real integrations (YouTube Data API, Video Indexer, Search upsert, Speech TTS, Maps, Cosmos writes).
- Add CEFR wordlists and classifier; implement IRT-like level estimation.
- Add Content Safety checks on search queries, transcripts, and generated sentences.

