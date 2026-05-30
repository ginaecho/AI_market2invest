"""
Generic LLM client supporting multiple providers via a unified interface.

Supported providers
-------------------
- **kimi**   → Moonshot AI (OpenAI-compatible SDK)
- **openai** → OpenAI (native SDK)
- **gemini** → Google Gemini (OpenAI-compatible endpoint)
- **claude** → Anthropic Claude (Anthropic SDK — no native OpenAI-compatible endpoint)

Configuration priority
----------------------
1. Environment variables: ``LLM_PROVIDER``, ``LLM_API_KEY``, ``LLM_MODEL``, ``LLM_BASE_URL``
2. ``config.yaml`` → ``llm:`` section
3. Provider defaults

Switching providers is a one-line change::

    export LLM_PROVIDER=gemini
    export LLM_API_KEY=...

SECURITY
--------
- API keys are read from environment only.
- All network calls use HTTPS.
- No eval/exec.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider defaults
# ---------------------------------------------------------------------------

_PROVIDER_DEFAULTS: Dict[str, Dict[str, str]] = {
    "kimi": {
        "env_key": "KIMI_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "kimi-latest",
    },
    "openai": {
        "env_key": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    },
    "gemini": {
        "env_key": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.0-flash",
    },
    "claude": {
        "env_key": "ANTHROPIC_API_KEY",
        "base_url": "",
        "default_model": "claude-sonnet-4-20250514",
    },
}


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------

def get_llm_config(config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Resolve LLM provider configuration from environment + config dict.

    Returns:
        Dict with keys: ``provider``, ``api_key``, ``model``, ``base_url``
    """
    cfg = config or {}

    # Provider priority: env > config > kimi fallback
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()
    if not provider:
        provider = (cfg.get("provider", "") or "").strip().lower()
    if not provider:
        provider = "kimi"

    p_defaults = _PROVIDER_DEFAULTS.get(provider, _PROVIDER_DEFAULTS["kimi"])

    # API key priority: generic LLM_API_KEY > provider-specific env var
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        api_key = os.getenv(p_defaults["env_key"], "").strip()

    # Model priority: env > config > provider default
    model = os.getenv("LLM_MODEL", "").strip()
    if not model:
        model = (cfg.get("model", "") or "").strip()
    if not model:
        model = p_defaults["default_model"]

    # Base URL priority: env > config > provider default
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    if not base_url:
        base_url = (cfg.get("base_url", "") or "").strip()
    if not base_url:
        base_url = p_defaults["base_url"]

    return {
        "provider": provider,
        "api_key": api_key,
        "model": model,
        "base_url": base_url,
    }


def is_llm_configured(config: Dict[str, Any] | None = None) -> bool:
    """Return True if a valid API key is available for the configured provider."""
    cfg = get_llm_config(config)
    return bool(cfg["api_key"])


# ---------------------------------------------------------------------------
# Low-level clients
# ---------------------------------------------------------------------------

def _create_openai_client(cfg: Dict[str, Any]) -> Any | None:
    """Create an OpenAI-compatible client (works for Kimi, OpenAI, Gemini)."""
    if not cfg["api_key"]:
        return None
    try:
        from openai import OpenAI  # type: ignore[import]
        return OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
    except ImportError:
        logger.warning("openai package not installed — LLM features disabled")
        return None


def _create_anthropic_client(cfg: Dict[str, Any]) -> Any | None:
    """Create an Anthropic client for Claude."""
    if not cfg["api_key"]:
        return None
    try:
        import anthropic  # type: ignore[import]
        return anthropic.Anthropic(api_key=cfg["api_key"])
    except ImportError:
        logger.warning("anthropic package not installed — Claude support disabled")
        return None


# ---------------------------------------------------------------------------
# Unified chat
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> str:
    """
    Extract bare JSON from a response that may contain markdown code blocks,
    explanatory text, or other wrapping.
    """
    import re

    # 1. Try to extract from ```json ... ``` or ``` ... ``` blocks
    code_block = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if code_block:
        candidate = code_block.group(1).strip()
        if candidate.startswith(("{", "[")):
            return candidate

    # 2. Find the first { or [ and the last } or ]
    start = -1
    for ch in ("[", "{"):
        idx = text.find(ch)
        if idx != -1 and (start == -1 or idx < start):
            start = idx
    end = -1
    for ch in ("]", "}"):
        idx = text.rfind(ch)
        if idx != -1 and idx > end:
            end = idx
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    # 3. Return as-is if nothing matched
    return text.strip()


def llm_chat(
    system_prompt: str,
    user_prompt: str,
    config: Dict[str, Any] | None = None,
    temperature: float = 0.3,
    max_tokens: int = 1500,
    response_format_json: bool = False,
    tracker: Any = None,
    stage: str = "",
    description: str = "",
) -> str:
    """
    Send a chat request to the configured LLM provider.

    Returns empty string if no API key is configured or the call fails.
    """
    cfg = get_llm_config(config)
    if not cfg["api_key"]:
        return ""

    provider = cfg["provider"]

    # Claude needs explicit JSON instructions (no native json_object mode)
    sp = system_prompt
    if response_format_json and provider == "claude":
        if "json" not in sp.lower():
            sp = sp + " Respond with valid JSON only. No markdown code blocks. No extra text."

    try:
        if provider == "claude":
            content = _chat_claude(
                cfg, sp, user_prompt, temperature, max_tokens,
                response_format_json, tracker, stage, description,
            )
        else:
            content = _chat_openai_compatible(
                cfg, sp, user_prompt, temperature, max_tokens,
                response_format_json, tracker, stage, description,
            )

        if response_format_json and content:
            content = _extract_json(content)
        return content
    except Exception as exc:
        logger.warning("%s API call failed: %s", provider.capitalize(), exc)
        return ""


# ---------------------------------------------------------------------------
# Provider-specific chat implementations
# ---------------------------------------------------------------------------

def _chat_openai_compatible(
    cfg: Dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    response_format_json: bool,
    tracker: Any,
    stage: str,
    description: str,
) -> str:
    client = _create_openai_client(cfg)
    if not client:
        return ""

    kwargs: Dict[str, Any] = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format_json:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content or ""

    if tracker is not None:
        try:
            usage = response.usage
            tracker.record_tokens(
                provider=cfg["provider"],
                model=cfg["model"],
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                stage=stage,
                description=description,
            )
        except Exception:
            tracker.record(
                provider=cfg["provider"],
                model=cfg["model"],
                input_text=system_prompt + "\n" + user_prompt,
                output_text=content,
                stage=stage,
                description=description,
            )
    return content


def _chat_claude(
    cfg: Dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
    response_format_json: bool,
    tracker: Any,
    stage: str,
    description: str,
) -> str:
    client = _create_anthropic_client(cfg)
    if not client:
        return ""

    message = client.messages.create(
        model=cfg["model"],
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=temperature,
    )

    content = ""
    for block in message.content:
        if hasattr(block, "text"):
            content += block.text

    if tracker is not None:
        try:
            tracker.record_tokens(
                provider="claude",
                model=cfg["model"],
                input_tokens=message.usage.input_tokens if message.usage else 0,
                output_tokens=message.usage.output_tokens if message.usage else 0,
                stage=stage,
                description=description,
            )
        except Exception:
            tracker.record(
                provider="claude",
                model=cfg["model"],
                input_text=system_prompt + "\n" + user_prompt,
                output_text=content,
                stage=stage,
                description=description,
            )
    return content


# ---------------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------------

def kimi_chat(
    system_prompt: str,
    user_prompt: str,
    model: str = "kimi-latest",
    temperature: float = 0.3,
    max_tokens: int = 1500,
    response_format_json: bool = False,
    tracker: Any = None,
    stage: str = "",
    description: str = "",
) -> str:
    """
    Backward-compatible alias that forces the **Kimi** provider.

    New code should call :func:`llm_chat` directly with a ``config`` dict.
    """
    return llm_chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        config={"provider": "kimi", "model": model},
        temperature=temperature,
        max_tokens=max_tokens,
        response_format_json=response_format_json,
        tracker=tracker,
        stage=stage,
        description=description,
    )
