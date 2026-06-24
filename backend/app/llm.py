"""LLM client: OpenRouter gateway with Cerebras provider pinning."""

import logging
import os
from typing import TypeVar

from dotenv import load_dotenv
from litellm import completion
from pydantic import BaseModel, ValidationError

load_dotenv()

log = logging.getLogger(__name__)

MODEL = os.getenv("MODEL", "openrouter/openai/gpt-oss-120b")
PROVIDERS = os.getenv("LLM_PROVIDERS", "Cerebras").split(",")
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))

EXTRA_BODY = {"provider": {"order": [p.strip() for p in PROVIDERS]}}

T = TypeVar("T", bound=BaseModel)


def chat(messages: list[dict], temperature: float | None = None) -> str:
    """Send messages and return the text response."""
    response = completion(
        model=MODEL,
        messages=messages,
        temperature=temperature or TEMPERATURE,
        reasoning_effort="low",
        extra_body=EXTRA_BODY,
    )
    return response.choices[0].message.content


def chat_structured(
    messages: list[dict],
    schema: type[T],
    temperature: float | None = None,
) -> T:
    """Send messages and return a validated Pydantic object.

    Re-prompts once on parse/validation failure.
    """
    for attempt in range(2):
        response = completion(
            model=MODEL,
            messages=messages,
            response_format=schema,
            temperature=temperature or TEMPERATURE,
            reasoning_effort="low",
            extra_body=EXTRA_BODY,
        )
        raw = response.choices[0].message.content
        try:
            return schema.model_validate_json(raw)
        except (ValidationError, ValueError) as e:
            if attempt == 0:
                log.warning("Structured output validation failed, re-prompting: %s", e)
                messages = messages + [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": (
                            f"Your response did not match the required schema. "
                            f"Error: {e}\n\nPlease return valid JSON matching "
                            f"the schema exactly."
                        ),
                    },
                ]
            else:
                raise ValueError(
                    f"Structured output failed after re-prompt: {e}"
                ) from e
