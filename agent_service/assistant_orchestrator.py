"""
Minimal Azure AI Agent Service orchestrator example for the Learning Agent.
Note: Requires azure-ai-openai (or the new agent library) and proper credentials.
This file is a template and is not wired into the Streamlit MVP.
"""

import os
from typing import List, Dict, Any

# Placeholder: pip package names and APIs are evolving for Agent Service.
# Keep as a template to illustrate shape of setup.

ASSISTANT_INSTRUCTIONS = (
    "Always align videos to CEFR and favorite characters. "
    "After watching, extract 5 novel words and generate a simple sentence per word."
)


def get_tools_contract() -> List[Dict[str, Any]]:
    # Mirrors openapi.yaml; define function tools for the agent here
    return [
        {"type": "function", "name": "search_youtube_videos", "parameters": {
            "type": "object", "properties": {
                "age": {"type": "integer"},
                "cefr": {"type": "string"},
                "characters": {"type": "array", "items": {"type": "string"}},
                "max": {"type": "integer", "default": 10}
            }, "required": ["age", "cefr"]
        }},
        {"type": "function", "name": "index_video", "parameters": {
            "type": "object", "properties": {"videoUrl": {"type": "string"}},
            "required": ["videoUrl"]
        }},
        {"type": "function", "name": "rank_video_by_level", "parameters": {
            "type": "object", "properties": {"transcriptId": {"type": "string"}, "cefr": {"type": "string"}},
            "required": ["transcriptId", "cefr"]
        }},
        {"type": "function", "name": "extract_top_words", "parameters": {
            "type": "object", "properties": {"transcriptId": {"type": "string"}, "count": {"type": "integer", "default": 5}, "cefr": {"type": "string"}},
            "required": ["transcriptId", "cefr"]
        }},
        {"type": "function", "name": "example_sentence", "parameters": {
            "type": "object", "properties": {"word": {"type": "string"}, "cefr": {"type": "string"}, "context": {"type": "object"}},
            "required": ["word", "cefr"]
        }},
        {"type": "function", "name": "update_progress", "parameters": {
            "type": "object", "properties": {
                "childId": {"type": "string"}, "videoId": {"type": "string"},
                "learnedWords": {"type": "array", "items": {"type": "string"}},
                "quizScore": {"type": "integer"}, "durationSec": {"type": "integer"}
            }, "required": ["childId", "videoId", "learnedWords", "durationSec"]
        }},
        {"type": "function", "name": "compute_level", "parameters": {
            "type": "object", "properties": {"childId": {"type": "string"}},
            "required": ["childId"]
        }},
        {"type": "function", "name": "find_local_academies", "parameters": {
            "type": "object", "properties": {"address": {"type": "string"}, "radiusMeters": {"type": "integer", "default": 3000}, "tags": {"type": "array", "items": {"type": "string"}}, "topK": {"type": "integer", "default": 10}},
            "required": ["address"]
        }},
        {"type": "function", "name": "play_cheer", "parameters": {
            "type": "object", "properties": {"voice": {"type": "string", "default": "child"}, "style": {"type": "string", "default": "cheerful"}}
        }},
        {"type": "function", "name": "parent_report", "parameters": {
            "type": "object", "properties": {"childId": {"type": "string"}, "period": {"type": "string", "enum": ["7d", "30d", "90d"]}},
            "required": ["childId"]
        }}
    ]


def create_learning_assistant() -> Dict[str, Any]:
    # Placeholder return dict shows what to provision via SDK/portal
    return {
        "name": "Kids English Learning Agent",
        "model": os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini"),
        "tools": get_tools_contract(),
        "instructions": ASSISTANT_INSTRUCTIONS,
    }

