"""Shared LLM client for classification and application extraction."""
import httpx

from .config import settings


def _ollama_chat(messages: list[dict], num_predict: int = 60) -> str:
    response = httpx.post(
        f"{settings.ollama_base_url.rstrip('/')}/api/chat",
        json={
            "model": settings.ollama_model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "keep_alive": "10m",
            "options": {"temperature": 0.2, "num_predict": num_predict},
        },
        timeout=60.0,
    )
    response.raise_for_status()
    return (response.json().get("message", {}).get("content") or "").strip()


def _gemini_chat(messages: list[dict], num_predict: int = 60) -> str:
    if not settings.gemini_api_key:
        raise ValueError("gemini_api_key is required when llm_provider=gemini")

    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    user_parts = [m["content"] for m in messages if m["role"] == "user"]

    body: dict = {
        "contents": [{"role": "user", "parts": [{"text": "\n\n".join(user_parts)}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": num_predict,
            "responseMimeType": "application/json",
        },
    }
    if system_parts:
        body["systemInstruction"] = {"parts": [{"text": "\n".join(system_parts)}]}

    model = settings.gemini_model
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    response = httpx.post(
        url,
        params={"key": settings.gemini_api_key},
        json=body,
        timeout=60.0,
    )
    response.raise_for_status()

    candidates = response.json().get("candidates", [])
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    return (parts[0].get("text") if parts else "") or ""


def _openrouter_chat(messages: list[dict], num_predict: int = 60) -> str:
    if not settings.openrouter_api_key:
        raise ValueError("openrouter_api_key is required when llm_provider=openrouter")

    response = httpx.post(
        f"{settings.openrouter_base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.openrouter_model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": num_predict,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    choices = response.json().get("choices", [])
    if not choices:
        return ""
    return (choices[0].get("message", {}).get("content") or "").strip()


def chat_json(messages: list[dict], num_predict: int = 60) -> str:
    if settings.llm_provider == "gemini":
        return _gemini_chat(messages, num_predict)
    if settings.llm_provider == "openrouter":
        return _openrouter_chat(messages, num_predict)
    return _ollama_chat(messages, num_predict)
