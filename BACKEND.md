Azure Functions — Tools API

Local dev
- Create venv, install deps, run with Core Tools.

Commands
```
cd functions
python -m venv .venv
. .\.venv\Scripts\activate
pip install -r requirements.txt
copy local.settings.json.example local.settings.json
func start
```

Endpoints
- POST `/tools/search_youtube_videos`
- POST `/tools/index_video`
- POST `/tools/rank_video_by_level`
- POST `/tools/extract_top_words`
- POST `/tools/example_sentence`
- POST `/tools/update_progress`
- POST `/tools/compute_level`
- POST `/tools/find_local_academies`
- POST `/tools/play_cheer`
- POST `/tools/parent_report`

Notes
- Implement YouTube, Video Indexer, Search upsert, Cosmos writes, Speech TTS, and Maps calls where TODOs are marked.
- Use `openapi.yaml` as the contract and to register tools with Azure AI Agent Service.
