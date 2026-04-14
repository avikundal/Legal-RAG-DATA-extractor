from __future__ import annotations

import os


class LLMClientError(Exception):
    pass


class OpenAILLMClient:
    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        api_key: str | None = None,
        max_output_tokens: int = 500,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.max_output_tokens = max_output_tokens

        if not self.api_key:
            raise LLMClientError(
                "OPENAI_API_KEY is not set. Provide api_key or export OPENAI_API_KEY."
            )

        try:
            from openai import OpenAI
        except Exception as e:
            raise LLMClientError(f"Failed to import openai package: {e}") from e

        self.client = OpenAI(api_key=self.api_key)

    def generate(self, prompt: str) -> str:
        if not prompt or not prompt.strip():
            raise LLMClientError("Prompt must be non-empty.")

        try:
            response = self.client.responses.create(
                model=self.model,
                input=prompt,
                temperature=0,
                max_output_tokens=self.max_output_tokens,
            )
        except Exception as e:
            raise LLMClientError(f"OpenAI API call failed: {e}") from e

        text = getattr(response, "output_text", None)

        if not text or not text.strip():
            try:
                parts = []
                for item in response.output:
                    content = getattr(item, "content", None) or []
                    for c in content:
                        if getattr(c, "type", None) == "output_text":
                            parts.append(getattr(c, "text", ""))
                text = "".join(parts).strip()
            except Exception:
                text = None

        if not text:
            raise LLMClientError("Model returned empty output.")

        return text.strip()
