"""Thin Amazon Bedrock runtime client (Converse API).

Kept deliberately small and model-agnostic: it takes a prompt string and returns
the model's text. All configuration (region, model id, AWS profile) comes from
:class:`BedrockConfig`, which reads the saved settings with environment-variable
overrides so the same build works across machines without code changes.

boto3 is imported lazily inside the call so that importing this module never
requires AWS to be configured — the app only touches Bedrock when a review runs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_REGION = "us-west-2"
# Cross-region inference profile for Claude Haiku 4.5 on Bedrock. Override with
# VPAT_BEDROCK_MODEL_ID or the bedrock_model_id setting to switch models.
DEFAULT_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"


class BedrockError(RuntimeError):
    """Any failure calling Bedrock or reading its response."""


# Standard env var boto3 uses for a Bedrock API key (bearer token).
BEARER_ENV = "AWS_BEARER_TOKEN_BEDROCK"


def _default_key_file() -> Path | None:
    """Shared-key drop-in location: ``bedrock_api_key.txt`` next to settings.json.

    This is the zero-config path for teammates — drop the shared key file beside
    the app (or the exe) and it is picked up automatically.
    """
    try:
        from vpat_reviewer.config.settings import default_settings_path

        return default_settings_path().parent / "bedrock_api_key.txt"
    except Exception:  # noqa: BLE001 - key file is optional; never fatal
        return None


@dataclass(frozen=True)
class BedrockConfig:
    region: str = DEFAULT_REGION
    model_id: str = DEFAULT_MODEL_ID
    profile: str = ""
    api_key: str = ""
    max_tokens: int = 4096
    temperature: float = 0.2

    @classmethod
    def from_settings(cls, settings: dict[str, Any] | None) -> BedrockConfig:
        """Build config from settings, letting env vars win for portability."""
        s = settings or {}
        env = os.environ

        def pick(env_key: str, setting_key: str, default: str) -> str:
            return str(env.get(env_key) or s.get(setting_key) or default)

        try:
            max_tokens = int(s.get("bedrock_max_tokens", 4096) or 4096)
        except (TypeError, ValueError):
            max_tokens = 4096

        return cls(
            region=pick("VPAT_BEDROCK_REGION", "bedrock_region", DEFAULT_REGION),
            model_id=pick("VPAT_BEDROCK_MODEL_ID", "bedrock_model_id", DEFAULT_MODEL_ID),
            profile=pick("VPAT_BEDROCK_PROFILE", "bedrock_profile", ""),
            api_key=cls._resolve_api_key(s),
            max_tokens=max_tokens,
        )

    @staticmethod
    def _resolve_api_key(s: dict[str, Any]) -> str:
        """Find a Bedrock API key: env var, then settings, then a shared key file."""
        env = os.environ
        key = (
            env.get(BEARER_ENV)
            or env.get("VPAT_BEDROCK_API_KEY")
            or str(s.get("bedrock_api_key") or "")
        )
        if key.strip():
            return key.strip()

        fp = env.get("VPAT_BEDROCK_API_KEY_FILE") or str(s.get("bedrock_api_key_file") or "")
        path = Path(fp) if fp else _default_key_file()
        if path and path.exists():
            try:
                return path.read_text(encoding="utf-8").strip()
            except OSError:
                return ""
        return ""


def _client(cfg: BedrockConfig) -> Any:
    try:
        import boto3
    except ImportError as e:  # pragma: no cover - dependency is declared
        raise BedrockError("boto3 is not installed; run `pip install boto3`.") from e

    # Auth precedence: Bedrock API key (portable, shareable) > named SSO/IAM
    # profile > the default credential chain (env keys / instance role).
    if cfg.api_key:
        # boto3/botocore authenticate Bedrock with the bearer token in this env
        # var; setting it in-process is the documented way to supply the key.
        os.environ[BEARER_ENV] = cfg.api_key
        session = boto3.Session(region_name=cfg.region)
    elif cfg.profile:
        session = boto3.Session(profile_name=cfg.profile, region_name=cfg.region)
    else:
        session = boto3.Session(region_name=cfg.region)
    return session.client("bedrock-runtime")


def invoke(prompt: str, cfg: BedrockConfig, *, system: str = "") -> str:
    """Send ``prompt`` to Bedrock and return the model's reply text.

    Raises :class:`BedrockError` on any transport/auth/shape failure so callers
    can fall back to the deterministic pipeline.
    """
    try:
        client = _client(cfg)
    except BedrockError:
        raise
    except Exception as e:  # ProfileNotFound / NoRegionError / etc.
        raise BedrockError(f"Bedrock client could not be created: {e}") from e

    kwargs: dict[str, Any] = {
        "modelId": cfg.model_id,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": cfg.max_tokens, "temperature": cfg.temperature},
    }
    if system:
        kwargs["system"] = [{"text": system}]

    try:
        response = client.converse(**kwargs)
    except Exception as e:  # boto3/botocore raise a wide range; normalize them.
        raise BedrockError(f"Bedrock call failed: {e}") from e

    try:
        return str(response["output"]["message"]["content"][0]["text"])
    except (KeyError, IndexError, TypeError) as e:
        raise BedrockError(f"Unexpected Bedrock response shape: {e}") from e
