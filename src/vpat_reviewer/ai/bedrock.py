"""The Amazon Bedrock assessor: the adapter that actually asks a model.

``BedrockAssessor`` is the :class:`RiskAssessor` the app uses by default. Under
it sits a deliberately small Converse-API client: it takes a prompt string and
returns the model's text, and knows nothing about VPATs. All configuration
(region, model id, AWS profile) comes from :class:`BedrockConfig`, which reads
the saved settings with environment-variable overrides so the same build works
across machines without code changes.

boto3 is imported lazily inside the call, so importing this module never requires
AWS to be configured — the app only touches Bedrock when a review runs.

**Credentials never come from settings.json.** That file is tracked in git and
the frozen app writes it beside the exe, so a token in it is a published token.
:meth:`BedrockConfig.from_settings` takes no key from settings even if someone
adds one by hand.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vpat_reviewer.ai.base import (
    AssessmentError,
    AssessmentRequest,
    RiskAssessment,
    TokenUsage,
)
from vpat_reviewer.ai.response import parse

DEFAULT_REGION = "us-west-2"
# NVIDIA Nemotron Nano 12B on Bedrock. Override with VPAT_BEDROCK_MODEL_ID or
# the bedrock_model_id setting to switch models.
#
# **This is a deliberate cost/latency trade, not the most accurate option.**
# Against the 59-model, 5-VPAT comparison in docs/model_eval, this model scores
# 67.6 avg quality and agrees with the crowd consensus on 2 of 5 documents, vs
# 86.0 / 4-of-5 for `us.anthropic.claude-opus-4-6-v1`. It is ~91x cheaper
# ($0.0009 vs $0.0785/doc) and ~7.5x faster (3.5s vs 26.4s). Where it diverges it
# tends to answer one category *lower* than the larger models -- on Google Docs
# it said "Needs Manual Review" where Opus 4.6 said "Need TAAP" -- and
# under-flagging is the unsafe direction for a procurement verdict.
#
# Those numbers predate the current rubric, and the rubric is what the model is
# graded against: re-run docs/model_eval after editing
# ai/data/risk_review_prompt.md before trusting the comparison, and before
# treating a swap here as free. `needs_human_review` defaults to True for
# exactly this reason.
#
# **Model-id form differs by model, so verify rather than pattern-match.** Some
# models need a cross-region *inference profile* id (the `us.` prefix) and reject
# the bare foundation-model id from the catalog: `anthropic.claude-opus-4-6-v1`
# is real and Converse still refuses it -- "Invocation ... with on-demand
# throughput isn't supported. Retry with the ID or ARN of an inference profile."
# The Nemotron models have no inference profile and take the bare id. Check with
# `aws bedrock list-inference-profiles` *and* `list-foundation-models`.
#
# A wrong id fails *silently in the product*: the Converse call raises,
# assess_result records a non-verdict, and every report falls back to the offline
# classifier with only a status-line note (§7b). --selftest does not catch it --
# it checks the adapter loads, not that the id answers. The cheap proof is one
# real review with `verdict_source` == "ai" in the audit log (§7d).
#
# NOTE: duplicated in config/settings.py::IDENTITY_DEFAULTS, because config must
# not import ai (the arrows point inward). A test pins the two together.
DEFAULT_MODEL_ID = "nvidia.nemotron-nano-12b-v2"

# Standard env var boto3 uses for a Bedrock API key (bearer token).
BEARER_ENV = "AWS_BEARER_TOKEN_BEDROCK"

# A model that stops mid-sentence returns invalid JSON, which is not a verdict.
# The rubric's schema is large; leave room for it.
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.2


class BedrockError(RuntimeError):
    """Any failure calling Bedrock or reading its response."""


def _default_key_file() -> Path | None:
    """Shared-key drop-in location: ``bedrock_api_key.txt`` next to settings.json.

    This is the zero-config path for teammates — drop the shared key file beside
    the app (or the exe) and it is picked up automatically. It is gitignored;
    settings.json is not, which is why the key lives here and not there.
    """
    try:
        from vpat_reviewer.config.settings import default_settings_path

        return default_settings_path().parent / "bedrock_api_key.txt"
    except Exception:  # noqa: BLE001 - key file is optional; never fatal
        return None


@contextmanager
def _bearer_token(token: str) -> Iterator[None]:
    """Expose ``token`` to botocore for the duration of one call, then put it back.

    botocore reads the bearer token from the environment, so supplying it means
    setting a process-wide variable. Restoring it afterwards keeps one review
    from silently changing how the rest of the process authenticates. The window
    covers client construction *and* the call, because assuming botocore reads
    the variable eagerly is a bet with no upside.
    """
    previous = os.environ.get(BEARER_ENV)
    os.environ[BEARER_ENV] = token
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(BEARER_ENV, None)
        else:
            os.environ[BEARER_ENV] = previous


@dataclass(frozen=True)
class BedrockConfig:
    region: str = DEFAULT_REGION
    model_id: str = DEFAULT_MODEL_ID
    profile: str = ""
    api_key: str = ""
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = DEFAULT_TEMPERATURE

    @classmethod
    def from_settings(cls, settings: dict[str, Any] | None) -> BedrockConfig:
        """Build config from settings, letting env vars win for portability.

        ``api_key`` is resolved from the environment and the key file only — see
        the module docstring. A ``bedrock_api_key`` in settings.json is ignored.
        """
        s = settings or {}
        env = os.environ

        def pick(env_key: str, setting_key: str, default: str) -> str:
            return str(env.get(env_key) or s.get(setting_key) or default)

        def number(setting_key: str, default: float) -> float:
            try:
                return float(s.get(setting_key, default))
            except (TypeError, ValueError):
                return default

        return cls(
            region=pick("VPAT_BEDROCK_REGION", "bedrock_region", DEFAULT_REGION),
            model_id=pick("VPAT_BEDROCK_MODEL_ID", "bedrock_model_id", DEFAULT_MODEL_ID),
            profile=pick("VPAT_BEDROCK_PROFILE", "bedrock_profile", ""),
            api_key=cls._resolve_api_key(),
            max_tokens=int(number("bedrock_max_tokens", DEFAULT_MAX_TOKENS)),
            temperature=number("bedrock_temperature", DEFAULT_TEMPERATURE),
        )

    @staticmethod
    def _resolve_api_key() -> str:
        """Find a Bedrock bearer token: env var, then a key file.

        Deliberately takes no ``settings`` argument. A key in settings.json would
        be a key in git, so there is no code path that could read one — that is
        what makes the rule enforceable rather than merely documented.
        """
        env = os.environ
        key = (env.get(BEARER_ENV) or env.get("VPAT_BEDROCK_API_KEY") or "").strip()
        if key:
            return key

        fp = env.get("VPAT_BEDROCK_API_KEY_FILE") or ""
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
        from botocore.config import Config as BotoConfig
    except ImportError as e:  # pragma: no cover - dependency is declared
        raise BedrockError("boto3 is not installed; run `pip install boto3`.") from e

    # Auth precedence: Bedrock API key (portable, shareable) > named SSO/IAM
    # profile > the default credential chain (env keys / instance role).
    # The key is already in the environment via _bearer_token() when present.
    if cfg.profile and not cfg.api_key:
        session = boto3.Session(profile_name=cfg.profile, region_name=cfg.region)
    else:
        session = boto3.Session(region_name=cfg.region)

    # Without timeouts a hung socket parks the GUI's worker thread forever, with
    # the progress bar at 58% and no way to cancel.
    return session.client(
        "bedrock-runtime",
        config=BotoConfig(
            connect_timeout=10,
            read_timeout=60,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


@dataclass(frozen=True)
class Reply:
    """A model's answer plus what the call cost, as Bedrock reported it."""

    text: str
    usage: TokenUsage | None = None


def _usage_from(response: dict[str, Any]) -> TokenUsage | None:
    """Read the Converse envelope's usage block, or ``None`` if it isn't there.

    Absent or malformed means unreported, not zero — a zero we invented would be
    logged as a measurement. Never raises: a usable verdict must not be lost
    because the accounting was unreadable.
    """
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return None
    try:
        latency = response.get("metrics", {}).get("latencyMs")
        return TokenUsage(
            input_tokens=int(usage["inputTokens"]),
            output_tokens=int(usage["outputTokens"]),
            latency_ms=int(latency) if latency is not None else None,
        )
    except (KeyError, TypeError, ValueError):
        return None


def _converse(prompt: str, cfg: BedrockConfig, system: str) -> Reply:
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
        text = str(response["output"]["message"]["content"][0]["text"])
    except (KeyError, IndexError, TypeError) as e:
        raise BedrockError(f"Unexpected Bedrock response shape: {e}") from e
    return Reply(text=text, usage=_usage_from(response))


def invoke(prompt: str, cfg: BedrockConfig, *, system: str = "") -> Reply:
    """Send ``prompt`` to Bedrock and return its reply text and token usage.

    Raises :class:`BedrockError` on any transport/auth/shape failure so callers
    can fall back to the deterministic pipeline.
    """
    if not cfg.api_key:
        return _converse(prompt, cfg, system)
    with _bearer_token(cfg.api_key):
        return _converse(prompt, cfg, system)


class BedrockAssessor:
    """A :class:`RiskAssessor` backed by Amazon Bedrock's Converse API."""

    def __init__(self, cfg: BedrockConfig | None = None) -> None:
        self._cfg = cfg or BedrockConfig.from_settings(None)
        # A plain attribute, not a @property: the port declares a mutable
        # `model_id: str`, and mypy --strict rejects a read-only property
        # against it.
        self.model_id = self._cfg.model_id

    def assess(self, request: AssessmentRequest) -> RiskAssessment:
        try:
            reply = invoke(request.prompt, self._cfg)
        except BedrockError as e:
            # The port speaks AssessmentError. That the provider was Bedrock, and
            # that it failed at the transport layer, is not the caller's problem
            # — only that there is no verdict, and why.
            raise AssessmentError(str(e)) from e
        return parse(reply.text, model_id=self._cfg.model_id, usage=reply.usage)
