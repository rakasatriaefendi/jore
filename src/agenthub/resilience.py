from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agenthub.storage import Storage


@dataclass(frozen=True, slots=True)
class HttpPolicy:
    code: int
    family: str
    category: str
    retryable: bool
    cooldown_seconds: int
    consumes_retry: bool


# Policy is deliberately conservative. The status-code meanings follow the
# JORE project requirements supplied by the user. Only genuinely transient
# provider/server conditions get automatic cooldown/retry treatment.
HTTP_POLICIES: dict[int, HttpPolicy] = {}


def _register(
    codes: list[int],
    family: str,
    category: str,
    *,
    retryable: bool = False,
    cooldown_seconds: int = 0,
    consumes_retry: bool = True,
) -> None:
    for code in codes:
        HTTP_POLICIES[code] = HttpPolicy(
            code,
            family,
            category,
            retryable,
            cooldown_seconds,
            consumes_retry,
        )


_register([100, 101, 102, 103], "1xx", "informational", consumes_retry=False)
_register(
    [200, 201, 202, 203, 204, 205, 206, 207, 208, 226],
    "2xx",
    "success",
    consumes_retry=False,
)
_register(
    [300, 301, 302, 303, 304, 305, 307, 308],
    "3xx",
    "redirect",
    consumes_retry=False,
)
_register([400], "4xx", "bad_request")
_register([401, 407], "4xx", "authentication")
_register([511], "5xx", "network_authentication")
_register([402], "4xx", "billing")
_register([403, 451], "4xx", "permission")
_register([404, 410], "4xx", "not_found")
_register([405, 406, 411, 412, 413, 414, 415, 416, 417, 421, 422, 423, 424, 426, 428, 431], "4xx", "request_contract")
_register([408], "4xx", "timeout", retryable=True, cooldown_seconds=20, consumes_retry=False)
_register([409], "4xx", "conflict", retryable=True, cooldown_seconds=5, consumes_retry=True)
_register([425], "4xx", "too_early", retryable=True, cooldown_seconds=10, consumes_retry=False)
_register([429], "4xx", "rate_limit", retryable=True, cooldown_seconds=120, consumes_retry=False)
_register([500], "5xx", "server_error", retryable=True, cooldown_seconds=30, consumes_retry=False)
_register([501, 505, 506, 510], "5xx", "server_capability")
_register([502], "5xx", "bad_gateway", retryable=True, cooldown_seconds=30, consumes_retry=False)
_register([503], "5xx", "service_unavailable", retryable=True, cooldown_seconds=60, consumes_retry=False)
_register([504], "5xx", "gateway_timeout", retryable=True, cooldown_seconds=45, consumes_retry=False)
_register([507], "5xx", "insufficient_storage", retryable=True, cooldown_seconds=120, consumes_retry=False)
_register([508], "5xx", "loop_detected", retryable=False, consumes_retry=True)


@dataclass(frozen=True, slots=True)
class FailureClassification:
    category: str
    http_status: int | None = None
    retryable: bool = False
    cooldown_seconds: int = 0
    consumes_retry: bool = True
    provider_transient: bool = False


class ProviderCooldownError(RuntimeError):
    def __init__(self, message: str, *, scope: str | None = None) -> None:
        super().__init__(message)
        self.scope = scope
        self.attempt_recorded = True


class LoopDetectedError(RuntimeError):
    pass


_HTTP_PATTERNS = [
    re.compile(r"(?i)\bHTTP(?:/\d(?:\.\d)?)?\s*(?:status|error)?\s*[:=]?\s*([1-5]\d\d)\b"),
    re.compile(r"(?i)\bstatus(?:\s+code)?\s*[:=]\s*([1-5]\d\d)\b"),
    re.compile(r"(?i)\bcode\s*[:=]\s*([1-5]\d\d)\b"),
    re.compile(r"(?i)\b(4\d\d|5\d\d)\s+(?:too many requests|unauthorized|forbidden|not found|request timeout|internal server error|bad gateway|service unavailable|gateway timeout|loop detected)\b"),
]


def extract_http_status(text: str) -> int | None:
    value = text or ""
    for pattern in _HTTP_PATTERNS:
        match = pattern.search(value)
        if match:
            try:
                return int(match.group(1))
            except (TypeError, ValueError):
                pass
    return None


def _retry_after_seconds(text: str, default: int) -> int:
    match = re.search(
        r"(?i)retry[- ]after(?:\s*[:=]|\s+)\s*(\d{1,5})\s*(?:s|sec|seconds?)?",
        text or "",
    )
    if not match:
        return default
    try:
        return max(1, min(3600, int(match.group(1))))
    except ValueError:
        return default


def classify_failure(text: str) -> FailureClassification:
    value = (text or "").strip()
    lower = value.lower()
    status = extract_http_status(value)
    if status is not None and status in HTTP_POLICIES:
        policy = HTTP_POLICIES[status]
        cooldown = policy.cooldown_seconds
        if status == 429:
            cooldown = _retry_after_seconds(value, cooldown)
        return FailureClassification(
            category=policy.category,
            http_status=status,
            retryable=policy.retryable,
            cooldown_seconds=cooldown,
            consumes_retry=policy.consumes_retry,
            provider_transient=(policy.cooldown_seconds > 0 and not policy.consumes_retry),
        )

    if any(token in lower for token in ("rate limit", "too many requests", "ratelimit", "quota exceeded")):
        return FailureClassification(
            category="rate_limit",
            http_status=429,
            retryable=True,
            cooldown_seconds=_retry_after_seconds(value, 120),
            consumes_retry=False,
            provider_transient=True,
        )
    if any(token in lower for token in ("timed out", "timeout", "time out")):
        return FailureClassification(
            category="timeout",
            retryable=True,
            cooldown_seconds=45,
            consumes_retry=False,
            provider_transient=True,
        )
    if any(token in lower for token in ("connection reset", "connection refused", "network unreachable", "temporary failure", "dns")):
        return FailureClassification(
            category="network",
            retryable=True,
            cooldown_seconds=30,
            consumes_retry=False,
            provider_transient=True,
        )
    if any(token in lower for token in ("unauthorized", "invalid token", "login required", "authentication")):
        return FailureClassification(category="authentication", http_status=401)
    if any(token in lower for token in ("forbidden", "permission denied", "access denied")):
        return FailureClassification(category="permission", http_status=403)
    if "not found" in lower:
        return FailureClassification(category="not_found", http_status=404)
    if "loop detected" in lower:
        return FailureClassification(category="loop_detected", http_status=508)
    return FailureClassification(category="runtime_error")


_QUALITY_TAGS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("factual", ("factual", "incorrect", "wrong", "false", "inaccurate", "hallucinat")),
    ("missing_evidence", ("citation", "source", "evidence", "verify", "unverified")),
    ("format", ("format", "structure", "separator", "json", "schema", "output format")),
    ("auth", ("auth", "token", "credential", "401", "unauthorized")),
    ("permission", ("permission", "403", "forbidden")),
    ("test", ("test", "assert", "failing", "failed test")),
    ("syntax", ("syntax", "parse", "compile", "indentation")),
    ("dependency", ("dependency", "module", "package", "import", "version conflict")),
    ("timeout", ("timeout", "timed out", "408", "504")),
    ("rate_limit", ("rate limit", "429", "too many requests")),
    ("not_found", ("404", "not found", "missing file", "missing endpoint")),
    ("incomplete", ("incomplete", "missing", "omits", "does not address", "never answers")),
)

_STOPWORDS = {
    "the", "and", "that", "this", "with", "from", "into", "then", "than", "for", "are", "was", "were",
    "atau", "yang", "dan", "dengan", "untuk", "dari", "pada", "ini", "itu", "karena", "harus", "tidak",
    "review", "verdict", "needs_fix", "response", "result", "answer", "output", "worker", "model",
}


def _quality_category(text: str) -> str:
    lower = (text or "").lower()
    tags = [name for name, markers in _QUALITY_TAGS if any(marker in lower for marker in markers)]
    return "+".join(tags[:3]) if tags else "quality"


def _stable_terms(text: str, limit: int = 10) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", (text or "").lower())
    seen: list[str] = []
    for word in words:
        if word in _STOPWORDS or word.isdigit():
            continue
        if word not in seen:
            seen.append(word)
        if len(seen) >= limit:
            break
    return seen


def fingerprint_failure(
    text: str,
    *,
    classification: FailureClassification | None = None,
    source: str = "runtime",
) -> str:
    classification = classification or classify_failure(text)
    # Stable protocol/system failures should fingerprint identically even when
    # providers phrase the surrounding sentence differently.
    if classification.http_status is not None:
        return f"{source}:{classification.category}:http{classification.http_status}"
    if classification.category != "runtime_error":
        return f"{source}:{classification.category}"
    terms = _stable_terms(text, 8)
    basis = f"{source}|runtime_error|{'/'.join(terms)}"
    digest = hashlib.sha256(basis.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"{source}:runtime_error:{digest}"


def fingerprint_review(text: str) -> str:
    status = extract_http_status(text)
    if status is not None:
        classification = classify_failure(text)
        return f"review:{classification.category}:http{status}"
    category = _quality_category(text)
    # Within one logical RunState, repeating the same quality category twice is
    # enough to stop blind retries. This catches paraphrased reviews such as
    # "endpoint returned 401" -> "still unauthorized" or repeated factual
    # corrections without requiring exact wording.
    if category != "quality":
        return f"review:{category}"
    terms = _stable_terms(text, 10)
    basis = f"review|quality|{'/'.join(terms)}"
    digest = hashlib.sha256(basis.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"review:quality:{digest}"


def provider_scope(provider: str, model: str | None = None) -> str:
    provider_key = re.sub(r"[^a-z0-9._-]+", "-", provider.lower()).strip("-") or "provider"
    if not model:
        return provider_key
    model_key = re.sub(r"[^a-z0-9._/-]+", "-", model.lower()).strip("-") or "model"
    return f"{provider_key}:{model_key}"


def cooldown_until(seconds: int) -> str:
    return (
        datetime.now(timezone.utc) + timedelta(seconds=max(1, seconds))
    ).isoformat(timespec="seconds")


def remaining_seconds(until: str) -> int:
    try:
        target = datetime.fromisoformat(until)
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        return max(0, int((target - datetime.now(timezone.utc)).total_seconds()))
    except (TypeError, ValueError):
        return 0


def is_loop_detected(
    storage: "Storage",
    run_state_id: str,
    fingerprint: str | None,
    *,
    threshold: int,
) -> tuple[bool, int]:
    if not fingerprint:
        return False, 0
    count = storage.count_failure_fingerprint(run_state_id, fingerprint)
    return count >= max(2, threshold), count
