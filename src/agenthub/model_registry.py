from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agenthub.dependencies import resolve_tool
from agenthub.storage import DATA_DIR


CACHE_PATH = DATA_DIR / "model_catalog.json"
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


@dataclass(slots=True)
class ModelInfo:
    provider: str
    model_id: str
    label: str
    description: str | None = None
    selectable: bool = True
    free: bool | None = None
    reasoning_levels: tuple[str, ...] = ()
    default_reasoning: str | None = None
    native_provider: str | None = None
    source: str = "cli"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ModelInfo":
        return cls(
            provider=str(value.get("provider") or ""),
            model_id=str(value.get("model_id") or ""),
            label=str(value.get("label") or value.get("model_id") or ""),
            description=value.get("description"),
            selectable=bool(value.get("selectable", True)),
            free=value.get("free"),
            reasoning_levels=tuple(value.get("reasoning_levels") or ()),
            default_reasoning=value.get("default_reasoning"),
            native_provider=value.get("native_provider"),
            source=str(value.get("source") or "cache"),
        )


@dataclass(slots=True)
class CatalogResult:
    provider: str
    models: list[ModelInfo]
    source: str
    warning: str | None = None


class ModelRegistry:
    """Credential-aware provider model discovery.

    Only small model metadata is persisted. Raw provider catalog payloads are
    never written to AgentHub storage.
    """

    def __init__(self, cache_path: Path = CACHE_PATH) -> None:
        self.cache_path = Path(cache_path).expanduser()
        self._memory: dict[str, CatalogResult] = {}

    def _load_cache(self) -> dict[str, Any]:
        if not self.cache_path.exists():
            return {}
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _save_provider_cache(self, provider: str, models: list[ModelInfo]) -> None:
        payload = self._load_cache()
        payload[provider] = [asdict(model) for model in models]
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _cached(self, provider: str) -> list[ModelInfo]:
        payload = self._load_cache().get(provider)
        if not isinstance(payload, list):
            return []
        result: list[ModelInfo] = []
        for item in payload:
            if isinstance(item, dict):
                model = ModelInfo.from_dict(item)
                model.source = "agenthub-cache"
                if model.model_id:
                    result.append(model)
        return result

    @staticmethod
    def _run(command: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            text=True,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )

    @staticmethod
    def _clean_json_text(raw: str) -> str:
        text = raw.strip()
        if not text:
            return text
        starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]
        if not starts:
            return text
        start = min(starts)
        end = max(text.rfind("}"), text.rfind("]"))
        if end < start:
            return text[start:]
        return text[start : end + 1]

    def codex_models(self, *, refresh: bool = False) -> CatalogResult:
        if not refresh and "codex" in self._memory:
            return self._memory["codex"]

        status = resolve_tool("codex")
        if not status.found or not status.path:
            cached = self._cached("codex")
            return CatalogResult(
                provider="codex",
                models=cached,
                source="agenthub-cache" if cached else "missing",
                warning="Codex CLI is not available." if not cached else "Codex CLI unavailable; showing cached catalog.",
            )

        discovery_source = "codex-debug-models"
        try:
            # Prefer a future stable machine-readable command if the installed
            # Codex exposes one. Codex 0.157.x does not currently provide it,
            # so AgentHub falls back to `debug models`.
            result = self._run(
                [status.path, "models", "list", "--json"],
                timeout=20,
            )
            if result.returncode == 0 and result.stdout.strip():
                discovery_source = "codex-models-json"
            else:
                result = self._run([status.path, "debug", "models"], timeout=90)
                discovery_source = "codex-debug-models"
        except (OSError, subprocess.TimeoutExpired) as exc:
            cached = self._cached("codex")
            return CatalogResult(
                provider="codex",
                models=cached,
                source="agenthub-cache" if cached else "error",
                warning=f"Could not query Codex model catalog: {exc}",
            )

        if result.returncode != 0:
            cached = self._cached("codex")
            detail = (result.stderr or result.stdout).strip().splitlines()
            message = detail[-1] if detail else "Codex model discovery failed."
            return CatalogResult(
                provider="codex",
                models=cached,
                source="agenthub-cache" if cached else "error",
                warning=message,
            )

        try:
            payload = json.loads(self._clean_json_text(result.stdout))
        except json.JSONDecodeError:
            cached = self._cached("codex")
            return CatalogResult(
                provider="codex",
                models=cached,
                source="agenthub-cache" if cached else "error",
                warning="Codex returned a model catalog AgentHub could not parse.",
            )

        entries = payload.get("models") if isinstance(payload, dict) else payload
        if not isinstance(entries, list):
            entries = []

        models: list[ModelInfo] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            model_id = str(entry.get("slug") or entry.get("model") or entry.get("id") or "").strip()
            if not model_id:
                continue
            visibility = str(entry.get("visibility") or "list").lower()
            selectable = visibility == "list"
            reasoning: list[str] = []
            for level in entry.get("supported_reasoning_levels") or []:
                if isinstance(level, dict):
                    effort = level.get("effort")
                else:
                    effort = level
                if isinstance(effort, str) and effort and effort not in reasoning:
                    reasoning.append(effort)

            models.append(
                ModelInfo(
                    provider="codex",
                    model_id=model_id,
                    label=str(entry.get("display_name") or entry.get("name") or model_id),
                    description=(
                        str(entry.get("description"))
                        if entry.get("description")
                        else None
                    ),
                    selectable=selectable,
                    free=None,
                    reasoning_levels=tuple(reasoning),
                    default_reasoning=(
                        str(entry.get("default_reasoning_level"))
                        if entry.get("default_reasoning_level")
                        else None
                    ),
                    native_provider="openai",
                    source=discovery_source,
                )
            )

        models.sort(
            key=lambda model: (
                not model.selectable,
                next(
                    (
                        int(entry.get("priority", 9999))
                        for entry in entries
                        if isinstance(entry, dict)
                        and str(entry.get("slug") or entry.get("model") or entry.get("id") or "") == model.model_id
                    ),
                    9999,
                ),
                model.label.lower(),
            )
        )

        selectable = [model for model in models if model.selectable]
        if selectable:
            self._save_provider_cache("codex", selectable)
            catalog = CatalogResult("codex", selectable, discovery_source)
            self._memory["codex"] = catalog
            return catalog

        cached = self._cached("codex")
        return CatalogResult(
            "codex",
            cached,
            "agenthub-cache" if cached else discovery_source,
            "Codex catalog did not expose any selectable models.",
        )

    @staticmethod
    def _pretty_model_name(model_id: str) -> str:
        tail = model_id.split("/", 1)[-1]
        pieces = re.split(r"[-_]", tail)
        output: list[str] = []
        acronyms = {"gpt", "glm", "qwen", "kimi", "mimo", "llama", "api", "ai"}
        for piece in pieces:
            if not piece:
                continue
            low = piece.lower()
            if low in acronyms:
                output.append(piece.upper())
            elif re.fullmatch(r"\d+(?:\.\d+)*", piece):
                output.append(piece)
            else:
                output.append(piece[:1].upper() + piece[1:])
        return " ".join(output) or model_id

    def opencode_models(self, *, refresh: bool = False) -> CatalogResult:
        if not refresh and "opencode" in self._memory:
            return self._memory["opencode"]

        status = resolve_tool("opencode")
        if not status.found or not status.path:
            cached = self._cached("opencode")
            return CatalogResult(
                provider="opencode",
                models=cached,
                source="agenthub-cache" if cached else "missing",
                warning="OpenCode CLI is not available." if not cached else "OpenCode CLI unavailable; showing cached catalog.",
            )

        command = [status.path, "models"]
        if refresh:
            command.append("--refresh")

        try:
            result = self._run(command, timeout=90)
        except (OSError, subprocess.TimeoutExpired) as exc:
            cached = self._cached("opencode")
            return CatalogResult(
                "opencode",
                cached,
                "agenthub-cache" if cached else "error",
                f"Could not query OpenCode models: {exc}",
            )

        if result.returncode != 0:
            cached = self._cached("opencode")
            detail = (result.stderr or result.stdout).strip().splitlines()
            message = detail[-1] if detail else "OpenCode model discovery failed."
            return CatalogResult(
                "opencode",
                cached,
                "agenthub-cache" if cached else "error",
                message,
            )

        models: list[ModelInfo] = []
        seen: set[str] = set()
        for raw_line in result.stdout.splitlines():
            line = ANSI_RE.sub("", raw_line).strip()
            if not line or "/" not in line or any(char.isspace() for char in line):
                continue
            model_id = line
            if model_id in seen:
                continue
            seen.add(model_id)
            native_provider = model_id.split("/", 1)[0]
            lower_id = model_id.lower()
            free = lower_id.endswith("-free") or "/free" in lower_id
            models.append(
                ModelInfo(
                    provider="opencode",
                    model_id=model_id,
                    label=self._pretty_model_name(model_id),
                    selectable=True,
                    free=free,
                    native_provider=native_provider,
                    source="opencode-cli",
                )
            )

        models.sort(key=lambda model: (model.native_provider or "", model.label.lower()))
        if models:
            self._save_provider_cache("opencode", models)
            catalog = CatalogResult("opencode", models, "opencode-cli")
            self._memory["opencode"] = catalog
            return catalog

        cached = self._cached("opencode")
        return CatalogResult(
            "opencode",
            cached,
            "agenthub-cache" if cached else "opencode-cli",
            "OpenCode did not return any model IDs.",
        )


    def opencode_configured_model(self) -> str | None:
        status = resolve_tool("opencode")
        if not status.found or not status.path:
            return None
        try:
            result = self._run([status.path, "debug", "config"], timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        raw = result.stdout.strip()
        if not raw:
            return None
        try:
            payload = json.loads(self._clean_json_text(raw))
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        model = payload.get("model")
        return model if isinstance(model, str) and "/" in model else None

    def default_codex_model(self) -> ModelInfo | None:
        result = self.codex_models(refresh=False)
        return result.models[0] if result.models else None

    def find_codex(self, model_id: str | None) -> ModelInfo | None:
        if not model_id:
            return None
        result = self.codex_models(refresh=False)
        return next((model for model in result.models if model.model_id == model_id), None)

    def find_opencode(self, model_id: str | None) -> ModelInfo | None:
        if not model_id:
            return None
        result = self.opencode_models(refresh=False)
        return next((model for model in result.models if model.model_id == model_id), None)
