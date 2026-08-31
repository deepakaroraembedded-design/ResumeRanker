from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

from resume_ranker.errors import ConfigurationError
from resume_ranker.models.config import RootConfig

_ENV_PREFIX = "ATS_"


def _to_nested_dict(flat: dict[str, Any]) -> dict[str, Any]:
    """Convert flat keys with '__' separators into a nested dictionary.

    Args:
        flat: Mapping from dotted/underscored keys to values.

    Returns:
        A nested dictionary suitable for unpacking as Pydantic constructor kwargs.
    """
    nested: dict[str, Any] = {}
    for key, value in flat.items():
        parts = key.lower().split("__")
        current = nested
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
    return nested


def _load_yaml_file(path: Path | None) -> dict[str, Any]:
    """Load a YAML configuration file if it exists and is readable.

    Returns an empty dict if *path* is None or does not exist. Raises
    ConfigurationError if the file exists but cannot be parsed.
    """
    if path is None or not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"invalid YAML in {path}: {exc}") from exc
    except OSError as exc:
        raise ConfigurationError(f"cannot read config file {path}: {exc}") from exc

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigurationError(f"config file {path} must contain a YAML mapping")
    return data


def _load_env_overrides() -> dict[str, Any]:
    """Collect environment variables prefixed with ATS_ and convert to nested dict.

    The prefix is stripped, the remaining key is lower-cased, and '__' is treated
    as a nesting separator. For example ``ATS_SCORING__WEIGHTS__S1=25`` becomes
    ``{"scoring": {"weights": {"s1": 25}}}``.
    """
    raw: dict[str, Any] = {}
    for key, value in os.environ.items():
        if key.startswith(_ENV_PREFIX):
            inner = key[len(_ENV_PREFIX) :]
            raw[inner] = value
    return _to_nested_dict(raw)


def _coerce_value(value: Any) -> Any:
    """Best-effort coercion of string values to JSON-compatible Python scalars."""
    if not isinstance(value, str):
        return value
    lower = value.lower()
    if lower in ("true", "false"):
        return lower == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def _coerce_nested(mapping: dict[str, Any]) -> dict[str, Any]:
    """Recursively coerce string leaves of a nested override dict."""
    result: dict[str, Any] = {}
    for key, value in mapping.items():
        if isinstance(value, dict):
            result[key] = _coerce_nested(value)
        else:
            result[key] = _coerce_value(value)
    return result


def _find_key_case_insensitive(base: dict[str, Any], key: str) -> str | None:
    """Return the key from *base* that matches *key* case-insensitively, if any."""
    lower = key.lower()
    for base_key in base:
        if base_key.lower() == lower:
            return base_key
    return None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge *override* into *base* recursively; override wins at leaves.

    Dict keys are matched case-insensitively so that environment variables
    such as ``ATS_SCORING__WEIGHTS__S1`` override the file key ``S1`` instead of
    creating a duplicate lowercase entry.
    """
    merged = dict(base)
    for key, value in override.items():
        matched_key = _find_key_case_insensitive(merged, key) or key
        if (
            matched_key in merged
            and isinstance(merged[matched_key], dict)
            and isinstance(value, dict)
        ):
            merged[matched_key] = _deep_merge(merged[matched_key], value)
        else:
            merged[matched_key] = value
    return merged


def _redact_secrets(config: RootConfig) -> dict[str, Any]:
    """Return a JSON-serialisable copy of the config with secret fields masked."""
    data = cast(dict[str, Any], json.loads(config.model_dump_json()))
    for section in ("llm",):
        section_data = data.get(section)
        if isinstance(section_data, dict):
            for secret_key in ("api_key", "api_secret"):
                if secret_key in section_data:
                    section_data[secret_key] = "***"
    return data


def _config_hash(data: dict[str, Any]) -> str:
    """Compute a stable SHA-256 hash of a JSON-serialisable config dict."""
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ConfigResolver:
    """Resolve effective configuration from file, environment and CLI flags.

    Precedence (highest to lowest): CLI flag overrides > environment variables
    (``ATS_*``) > YAML config file > Pydantic defaults in ``RootConfig``.
    The effective config is hashed and the hash is recorded in the run manifest.
    """

    def __init__(self, file_path: Path | None = None) -> None:
        """Create a resolver tied to an optional YAML config file.

        Args:
            file_path: Path to the YAML configuration file. If None the
                resolver falls back to environment variables and defaults.
        """
        self.file_path = file_path

    def resolve(self, cli_overrides: dict[str, Any] | None = None) -> tuple[RootConfig, str]:
        """Resolve the full configuration and return it with its hash.

        Args:
            cli_overrides: Nested mapping of overrides supplied by CLI flags.

        Returns:
            A tuple of ``(RootConfig, config_hash)``.

        Raises:
            ConfigurationError: If the merged configuration fails Pydantic
                validation. The error message includes the field path and is
                suitable for printing as a CLI error (FR-1003).
        """
        file_config = _load_yaml_file(self.file_path)
        env_config = _coerce_nested(_load_env_overrides())
        merged = _deep_merge(file_config, env_config)
        if cli_overrides:
            merged = _deep_merge(merged, cli_overrides)
        try:
            config = RootConfig.model_validate(merged)
        except Exception as exc:
            raise ConfigurationError(f"configuration invalid: {exc}") from exc
        safe_data = _redact_secrets(config)
        return config, _config_hash(safe_data)
