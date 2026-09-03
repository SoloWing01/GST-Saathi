"""Dual LLM client with automatic fallback between Groq and Google Gemini.

Primary: Groq free tier (fast, good for structured extraction).
Fallback: Google Gemini free tier (when Groq is rate-limited or exhausted).

Usage:
    from agent.llm_client import llm_complete
    response = await llm_complete("Extract fields from this notice: ...")

The client tracks which provider is active and automatically switches
when one is exhausted. Both providers are tried in order per request
only when the primary fails — within a single call, it tries Groq first,
then Gemini.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from enum import Enum
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)


class Provider(str, Enum):
    GROQ = "groq"
    GOOGLE = "google"


class LLMClient:
    """Manages dual LLM providers with automatic fallback.

    Providers can be configured from explicit keys (per-tenant) or from
    environment variables when no keys are provided (default single-tenant).
    """

    def __init__(self, tenant=None) -> None:
        self._groq_client = None
        self._google_client = None
        self._active_provider: Provider | None = None
        self._groq_exhausted_until: float = 0.0
        self._google_exhausted_until: float = 0.0

        # Every user MUST provide their own LLM keys. We do NOT fall back to
        # server-side env values when the tenant supplies none.
        if tenant is not None:
            groq_key = (tenant.groq_api_key or "").strip()
            google_key = (tenant.google_api_key or "").strip()
            self._groq_model = (tenant.groq_model or "").strip() or "qwen/qwen3.6-27b"
            self._google_model = (tenant.google_model or "").strip() or "gemini-3.6-flash"
        else:
            # The standalone/default client without a tenant still reads env so
            # the app can boot for diagnostics, but the per-user flow always
            # passes a tenant whose keys are user-supplied.
            groq_key = os.getenv("GROQ_API_KEY", "").strip()
            google_key = os.getenv("GOOGLE_API_KEY", "").strip()
            self._groq_model = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")
            self._google_model = os.getenv("GOOGLE_MODEL", "gemini-3.6-flash")

        self._init_providers(groq_key, google_key)

    def _init_providers(self, groq_key: str, google_key: str) -> None:
        """Initialize whichever providers have API keys configured."""
        if groq_key:
            try:
                import groq

                self._groq_client = groq.Groq(api_key=groq_key)
                log.info("Groq client initialized (model: %s)", self._groq_model)
            except Exception as e:
                log.warning("Failed to init Groq client: %s", e)

        if google_key:
            try:
                from google import genai

                self._google_client = genai.Client(api_key=google_key)
                log.info("Google Gemini client initialized (model: %s)", self._google_model)
            except Exception as e:
                log.warning("Failed to init Google Gemini client: %s", e)

        # Determine initial active provider
        if self._groq_client:
            self._active_provider = Provider.GROQ
        elif self._google_client:
            self._active_provider = Provider.GOOGLE
        else:
            log.warning("No LLM providers configured — LLM calls will fail")

    @property
    def active_provider(self) -> Provider | None:
        return self._active_provider

    @property
    def has_providers(self) -> bool:
        return self._groq_client is not None or self._google_client is not None

    def _is_available(self, provider: Provider) -> bool:
        """Check if a provider is configured and not temporarily exhausted."""
        now = time.time()
        if provider == Provider.GROQ:
            if not self._groq_client:
                return False
            if now < self._groq_exhausted_until:
                return False
            return True
        elif provider == Provider.GOOGLE:
            if not self._google_client:
                return False
            if now < self._google_exhausted_until:
                return False
            return True
        return False

    def _mark_exhausted(self, provider: Provider, cooldown_seconds: float = 60.0) -> None:
        """Mark a provider as temporarily exhausted."""
        expiry = time.time() + cooldown_seconds
        if provider == Provider.GROQ:
            self._groq_exhausted_until = expiry
            log.warning("Groq marked exhausted for %ds", cooldown_seconds)
        elif provider == Provider.GOOGLE:
            self._google_exhausted_until = expiry
            log.warning("Google Gemini marked exhausted for %ds", cooldown_seconds)

        # Switch active provider if the exhausted one was active
        if self._active_provider == provider:
            self._switch_provider()

    def _switch_provider(self) -> None:
        """Switch to the other provider."""
        if self._active_provider == Provider.GROQ and self._is_available(Provider.GOOGLE):
            self._active_provider = Provider.GOOGLE
            log.info("Switched active provider: Groq -> Google Gemini")
        elif self._active_provider == Provider.GOOGLE and self._is_available(Provider.GROQ):
            self._active_provider = Provider.GROQ
            log.info("Switched active provider: Google Gemini -> Groq")
        else:
            log.error("No available providers after exhaustion")

    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> tuple[str, str]:
        """Send a chat completion request with automatic fallback.

        Returns:
            Tuple of (response_text, provider_name_used).

        Raises:
            RuntimeError: If both providers fail or neither is configured.
        """
        if not self.has_providers:
            raise RuntimeError("No LLM providers configured. Set GROQ_API_KEY or GOOGLE_API_KEY.")

        # Build provider attempt order: active first, then the other
        providers = self._attempt_order()

        last_error = None
        for provider in providers:
            try:
                if provider == Provider.GROQ:
                    result = await self._call_groq(prompt, system, temperature, max_tokens)
                    return result, Provider.GROQ.value
                elif provider == Provider.GOOGLE:
                    result = await self._call_google(prompt, system, temperature, max_tokens)
                    return result, Provider.GOOGLE.value
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                log.warning("Provider %s failed: %s", provider.value, e)

                # Determine if this is a rate limit / quota / too-large error (switch provider)
                if any(kw in error_str for kw in [
                    "429", "413", "rate limit", "quota", "too many requests",
                    "resource_exhausted", "deadline_exceeded", "request too large",
                    "requests per minute", "requests per day", "tokens per minute",
                    "reduce your message size",
                ]):
                    cooldown = 120 if "per day" in error_str else 60
                    self._mark_exhausted(provider, cooldown_seconds=cooldown)
                else:
                    # Non-rate-limit error — mark briefly exhausted and try next
                    self._mark_exhausted(provider, cooldown_seconds=10)

        raise RuntimeError(
            f"All LLM providers failed. Last error: {last_error}"
        )

    def _attempt_order(self) -> list[Provider]:
        """Return providers in attempt order: available ones first."""
        primary = self._active_provider or Provider.GROQ
        secondary = Provider.GOOGLE if primary == Provider.GROQ else Provider.GROQ

        order = []
        if self._is_available(primary):
            order.append(primary)
        if self._is_available(secondary):
            order.append(secondary)

        # If neither is available due to cooldown, try both anyway (cooldown might just expired)
        if not order:
            if self._groq_client:
                order.append(Provider.GROQ)
            if self._google_client:
                order.append(Provider.GOOGLE)

        return order

    async def _call_groq(
        self, prompt: str, system: str, temperature: float, max_tokens: int
    ) -> str:
        """Make a completion call to Groq (runs synchronous SDK in thread)."""
        def _sync_call():
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            response = self._groq_client.chat.completions.create(
                model=self._groq_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        return await asyncio.to_thread(_sync_call)

    async def _call_google(
        self, prompt: str, system: str, temperature: float, max_tokens: int
    ) -> str:
        """Make a completion call to Google Gemini (runs synchronous SDK in thread)."""
        def _sync_call():
            contents = []
            if system:
                contents.append(
                    {"role": "user", "parts": [{"text": system}]}
                )
                contents.append(
                    {"role": "model", "parts": [{"text": "Understood. I will follow these instructions."}]}
                )
            contents.append(
                {"role": "user", "parts": [{"text": prompt}]}
            )
            response = self._google_client.models.generate_content(
                model=self._google_model,
                contents=contents,
                config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )
            return response.text or ""
        return await asyncio.to_thread(_sync_call)


# Singleton instances, keyed by tenant id. "default" is the env-based client.
_llm_clients: dict[str, LLMClient] = {}
_clients_lock = asyncio.Lock()


def get_llm_client(tenant_id: str = "default") -> LLMClient:
    """Get or create an LLM client for a tenant.

    Every user must supply their own LLM keys. If the tenant has no usable key,
    we raise so the caller surfaces a clear "provide your LLM key" message
    instead of silently falling back to shared server keys.
    """
    tenant_id = (tenant_id or "default").strip() or "default"

    global _llm_clients

    # Import lazily to avoid a circular import at module load time.
    from tenancy import get_tenant

    existing = _llm_clients.get(tenant_id)
    if existing is not None:
        return existing

    tenant = get_tenant(tenant_id)

    # A tenant must have provided its own LLM key. No env fallback.
    if tenant is None or not tenant.has_llm():
        raise RuntimeError(
            "No LLM API key configured for this session. Open Settings and "
            "provide a Groq or Google Gemini API key to continue."
        )

    client = LLMClient(tenant=tenant)
    if not client.has_providers:
        raise RuntimeError(
            "Could not initialize the LLM provider with the keys provided. "
            "Check that your Groq / Google Gemini API key is valid."
        )

    _llm_clients[tenant_id] = client
    return client


async def llm_complete(
    prompt: str,
    system: str = "",
    temperature: float = 0.1,
    max_tokens: int = 2048,
    tenant_id: str = "default",
) -> tuple[str, str]:
    """Convenience function — delegates to the tenant's client.

    Returns:
        Tuple of (response_text, provider_name_used).
    """
    client = get_llm_client(tenant_id)
    return await client.complete(prompt, system, temperature, max_tokens)
