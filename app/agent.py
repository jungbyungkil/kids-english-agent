import os, json, asyncio, httpx
from dotenv import load_dotenv
from .prompts import SYSTEM_PROMPT

USE_FUNCTION_TOOLS = os.getenv("USE_FUNCTION_TOOLS", "false").lower() in ("1", "true", "yes")
if USE_FUNCTION_TOOLS:
    from .azure_tools import TOOLS_SPEC, tool_router  # route via Azure Functions
else:
    from .tools import TOOLS_SPEC, tool_router        # built-in demo tools

load_dotenv()
AOAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AOAI_KEY = os.getenv("AZURE_OPENAI_API_KEY")
DEPLOY = os.getenv("AZURE_OPENAI_DEPLOYMENT")

# Allow overriding API version from env; default to a stable tools-capable chat version
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")


async def _aoai_chat(messages, tools=None, tool_choice="auto"):
    url = f"{AOAI_ENDPOINT}/openai/deployments/{DEPLOY}/chat/completions?api-version={API_VERSION}"
    headers = {"Content-Type": "application/json", "api-key": AOAI_KEY}
    payload = {"messages": messages, "temperature": 0.2}
    disable_tools = os.getenv("AOAI_DISABLE_TOOLS", "false").lower() in ("1", "true", "yes")
    if tools and not disable_tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json()
            except Exception:
                detail = e.response.text
            raise RuntimeError(f"Azure OpenAI error {e.response.status_code}: {detail}") from e
        data = resp.json()
        choice = data["choices"][0]
        return choice


async def chat_with_agent(history):
    # Ensure system prompt is present
    messages = []
    system_added = any(m.get("role") == "system" for m in history)
    if not system_added:
        messages.append({"role": "system", "content": SYSTEM_PROMPT})
    else:
        # replace the first system with our system prompt to ensure consistency
        replaced = False
        for m in history:
            if m.get("role") == "system" and not replaced:
                messages.append({"role": "system", "content": SYSTEM_PROMPT})
                replaced = True
            else:
                messages.append(m)
    if not system_added:
        messages.extend(history)

    # First turn
    choice = await _aoai_chat(messages, tools=TOOLS_SPEC, tool_choice="auto")
    msg = choice["message"]

    # Tool loop (max 6)
    for _ in range(6):
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            break
        # First, append the assistant message that requested tools
        messages.append({
            "role": "assistant",
            "content": msg.get("content", ""),
            "tool_calls": tool_calls,
        })
        # Then execute tools and append tool results that reference the ids
        for tc in tool_calls:
            name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"] or "{}")
            result = await tool_router(name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "name": name,
                "content": json.dumps(result, ensure_ascii=False),
            })
        # Follow-up to get final answer
        choice = await _aoai_chat(messages, tools=TOOLS_SPEC, tool_choice="auto")
        msg = choice["message"]

    # Return final assistant content (fallback if empty)
    content = msg.get("content") or "응답이 비었습니다. 설정을 확인하세요."
    return content
