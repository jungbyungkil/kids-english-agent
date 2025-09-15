import os
import json
from typing import Any, Dict

import httpx
from urllib.parse import urlencode


BASE = os.getenv("TOOLS_BASE_URL", "https://app-service-kingbk-fpe2dahdgpabgxbd.swedencentral-01.azurewebsites.net")
FUNC_CODE = os.getenv("FUNCTIONS_CODE")  # optional function key for AuthLevel.FUNCTION


TOOLS_SPEC = [
    {"type": "function", "function": {"name": "search_youtube_videos", "parameters": {
        "type": "object", "properties": {
            "age": {"type": "integer"},
            "cefr": {"type": "string"},
            "characters": {"type": "array", "items": {"type": "string"}},
            "max": {"type": "integer", "default": 10}
        }, "required": ["age", "cefr"]
    }}},
    {"type": "function", "function": {"name": "index_video", "parameters": {
        "type": "object", "properties": {"videoUrl": {"type": "string"}},
        "required": ["videoUrl"]
    }}},
    {"type": "function", "function": {"name": "rank_video_by_level", "parameters": {
        "type": "object", "properties": {"transcriptId": {"type": "string"}, "cefr": {"type": "string"}},
        "required": ["transcriptId", "cefr"]
    }}},
    {"type": "function", "function": {"name": "extract_top_words", "parameters": {
        "type": "object", "properties": {"transcriptId": {"type": "string"}, "count": {"type": "integer", "default": 5}, "cefr": {"type": "string"}},
        "required": ["transcriptId", "cefr"]
    }}},
    {"type": "function", "function": {"name": "example_sentence", "parameters": {
        "type": "object", "properties": {"word": {"type": "string"}, "cefr": {"type": "string"}, "context": {"type": "object"}},
        "required": ["word", "cefr"]
    }}},
    {"type": "function", "function": {"name": "update_progress", "parameters": {
        "type": "object", "properties": {
            "childId": {"type": "string"}, "videoId": {"type": "string"},
            "learnedWords": {"type": "array", "items": {"type": "string"}},
            "quizScore": {"type": "integer"}, "durationSec": {"type": "integer"}
        }, "required": ["childId", "videoId", "learnedWords", "durationSec"]
    }}},
    {"type": "function", "function": {"name": "compute_level", "parameters": {
        "type": "object", "properties": {"childId": {"type": "string"}},
        "required": ["childId"]
    }}},
    {"type": "function", "function": {"name": "find_local_academies", "parameters": {
        "type": "object", "properties": {"address": {"type": "string"}, "radiusMeters": {"type": "integer", "default": 3000}, "tags": {"type": "array", "items": {"type": "string"}}, "topK": {"type": "integer", "default": 10}},
        "required": ["address"]
    }}},
    {"type": "function", "function": {"name": "play_cheer", "parameters": {
        "type": "object", "properties": {"voice": {"type": "string", "default": "child"}, "style": {"type": "string", "default": "cheerful"}}
    }}},
    {"type": "function", "function": {"name": "parent_report", "parameters": {
        "type": "object", "properties": {"childId": {"type": "string"}, "period": {"type": "string", "enum": ["7d", "30d", "90d"]}},
        "required": ["childId"]
    }}},
    {"type": "function", "function": {"name": "say_word", "parameters": {
        "type": "object", "properties": {"word": {"type": "string"}, "voice": {"type": "string"}, "style": {"type": "string"}},
        "required": ["word"]
    }}},
    {"type": "function", "function": {"name": "search_academies_ai", "parameters": {
        "type": "object", "properties": {"region": {"type": "string"}, "query": {"type": "string"}, "topK": {"type": "integer", "default": 5}},
        "required": ["region"]
    }}},
    {"type": "function", "function": {"name": "save_profile", "parameters": {
        "type": "object", "properties": {
            "childId": {"type": "string"},
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "region": {"type": "string"},
            "study": {"type": "string"},
            "characters": {"type": "array", "items": {"type": "string"}},
            "cefr": {"type": "string"},
            "interest": {"type": "integer"}
        },
        "required": ["childId", "name", "age", "region", "study", "characters", "cefr"]
    }}},
    {"type": "function", "function": {"name": "load_profile", "parameters": {
        "type": "object", "properties": {"childId": {"type": "string"}},
        "required": ["childId"]
    }}},
    {"type": "function", "function": {"name": "save_prefs", "parameters": {
        "type": "object", "properties": {
            "childId": {"type": "string"},
            "recent_videos": {"type": "array", "items": {"type": "object"}},
            "favorite_videos": {"type": "array", "items": {"type": "object"}}
        },
        "required": ["childId"]
    }}},
    {"type": "function", "function": {"name": "load_prefs", "parameters": {
        "type": "object", "properties": {"childId": {"type": "string"}},
        "required": ["childId"]
    }}}
]


async def tool_router(name: str, args: Dict[str, Any]):
    base_paths = [f"{BASE}/tools/{name}", f"{BASE}/api/tools/{name}"]
    last_err = None
    async with httpx.AsyncClient(timeout=30) as client:
        for url in base_paths:
            try:
                u = url
                if FUNC_CODE:
                    sep = '&' if '?' in u else '?'
                    u = f"{u}{sep}{urlencode({'code': FUNC_CODE})}"
                resp = await client.post(u, json=args)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                last_err = f"{e.response.status_code} {getattr(e.response,'text', '')[:200]}"
            except Exception as e:
                last_err = str(e)
                continue
    raise RuntimeError(f"tool_router failed for {name}: {last_err}")
