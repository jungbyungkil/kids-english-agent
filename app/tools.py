from typing import Any, Dict
from .search_client import search_docs

TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": "RAG: 내부 지식(FAQ/커리큘럼)에서 관련 문서를 검색",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "질의문"},
                    "top": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "quick_calc",
            "description": "간단 계산기 (사칙연산)",
            "parameters": {
                "type": "object",
                "properties": { "expr": {"type": "string"} },
                "required": ["expr"]
            }
        }
    }
]

async def tool_router(name: str, args: Dict[str, Any]):
    if name == "search_docs":
        return {"results": await search_docs(args["query"], args.get("top", 5))}
    if name == "quick_calc":
        try:
            return {"result": str(eval(args["expr"], {"__builtins__": {}}))}
        except Exception as e:
            return {"error": str(e)}
    return {"error": f"unknown tool {name}"}
