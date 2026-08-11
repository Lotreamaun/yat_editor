"""
Клиент Yandex Cloud LLM (OpenAI-совместимый API) для глубокой коррекции текста.
"""

from typing import Optional

from openai import AsyncOpenAI

from config.config import (
    YANDEX_CLOUD_FOLDER,
    YANDEX_CLOUD_API_KEY,
    YANDEX_CLOUD_MODEL,
    YANDEX_LLM_BASE_URL,
    YANDEX_LLM_MAX_TOKENS,
    logger,
)

CORRECTION_PROMPT = (
    "Исправь грамматические, орфографические и пунктуационные ошибки в тексте. "
    "Вноси минимальные правки: не меняй слова и их порядок, не пересказывай текст. "
    "Верни только исправленный текст без пояснений."
)


class YandexLLMClient:
    """Асинхронный клиент глубокой коррекции через Yandex GPT."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        folder_id: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else YANDEX_CLOUD_API_KEY
        self.folder_id = folder_id if folder_id is not None else YANDEX_CLOUD_FOLDER
        self.model = model if model is not None else YANDEX_CLOUD_MODEL
        self.base_url = base_url if base_url is not None else YANDEX_LLM_BASE_URL
        self.max_tokens = max_tokens if max_tokens is not None else YANDEX_LLM_MAX_TOKENS
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                default_headers={"OpenAI-Project": self.folder_id},
            )
        return self._client

    def available(self) -> bool:
        """Глубокая правка доступна, только если ключ реально задан."""
        return bool(self.api_key) and bool(self.folder_id) and not self.api_key.startswith("<")

    async def correct_text(self, text: str) -> str:
        """Возвращает исправленный текст или бросает исключение."""
        client = self._get_client()
        response = await client.chat.completions.create(
            model=f"gpt://{self.folder_id}/{self.model}",
            messages=[
                {"role": "system", "content": CORRECTION_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.3,
            max_tokens=self.max_tokens,
        )
        corrected = response.choices[0].message.content
        if not corrected or not corrected.strip():
            raise ValueError("LLM вернул пустой ответ")
        return corrected.strip()


llm_client = YandexLLMClient()
