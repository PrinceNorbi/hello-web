import os

import httpx

PROMPT_MAX = 1000
TIMEOUT = 120  # seconds; CPU-only models can be slow to answer


def model() -> str:
    return os.environ.get("OLLAMA_MODEL", "qwen3.8")


async def generate(prompt: str) -> str:
    """Ask the local Ollama server for a single, non-streamed completion."""
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(
            f"{url}/api/generate",
            json={
                "model": model(),
                "prompt": prompt,
                "stream": False,
                "think": False,
                "options": {"enable_thinking": False},
            },
        )
        response.raise_for_status()
        return response.json()["response"]
