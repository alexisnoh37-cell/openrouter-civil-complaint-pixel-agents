import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")


DEFAULT_MODEL = "openai/gpt-4o-mini"


class OpenRouterClient:
    """Small wrapper around the OpenAI SDK configured for OpenRouter."""

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)

        if self.api_key:
            self.client: AsyncOpenAI | None = AsyncOpenAI(
                api_key=self.api_key,
                base_url="https://openrouter.ai/api/v1",
            )
        else:
            self.client = None

    async def json_chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        if not self.client:
            raise RuntimeError(
                "OPENROUTER_API_KEY가 설정되지 않았습니다. backend/.env 파일에 API 키를 입력해 주세요."
            )

        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_prompt.strip()},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"LLM 응답을 JSON으로 해석할 수 없습니다: {content}") from exc


openrouter = OpenRouterClient()
