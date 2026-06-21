# ============================================================
#  ollama_client.py — Talks to Qwen3 running via Ollama
#
#  Now supports tool calling: Qwen3 can request that Python
#  functions be run, and the result gets fed back to it.
# ============================================================

import requests

OLLAMA_HOST = "http://localhost:11434"
MODEL_NAME = "qwen3"
TIMEOUT_SECONDS = 300


def chat(messages: list[dict], system_prompt: str = None, tools: list[dict] = None) -> dict:
    """
    Send a conversation to Qwen3 and return its raw response message.

    Args:
        messages: conversation history, e.g. [{"role": "user", "content": "..."}]
        system_prompt: optional instructions prepended to the conversation
        tools: optional list of tool definitions in Ollama's schema

    Returns:
        The "message" dict from Ollama's response. This may contain:
          - "content": the model's text reply (can be empty if it's calling a tool)
          - "tool_calls": a list of tool calls the model wants to make (if any)

    Raises:
        ConnectionError if Ollama is not running.
    """
    payload_messages = list(messages)
    if system_prompt:
        payload_messages = [{"role": "system", "content": system_prompt}] + payload_messages

    payload = {
        "model": MODEL_NAME,
        "messages": payload_messages,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 1024,
        }
    }

    if tools:
        payload["tools"] = tools

    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload,
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()

    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            "Cannot reach Ollama. Is it running? Try: ollama serve"
        )
    except requests.exceptions.Timeout:
        raise TimeoutError(
            f"Ollama did not respond within {TIMEOUT_SECONDS}s."
        )

    data = response.json()

    try:
        return data["message"]
    except (KeyError, TypeError) as e:
        raise RuntimeError(f"Unexpected response format from Ollama: {data}") from e


def is_ollama_running() -> bool:
    """Quick health check — returns True if Ollama is reachable."""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        return r.status_code == 200
    except requests.exceptions.ConnectionError:
        return False