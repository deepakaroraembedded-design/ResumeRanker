from __future__ import annotations

import re
import string
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from resume_ranker.llm.security import (
    remove_quarantined_spans,
    strip_control_chars,
    truncate,
)

_TEMPLATE_DIR = Path(__file__).with_suffix("").parent / "prompts"


@dataclass(frozen=True)
class PromptTemplate:
    """A versioned prompt template.

    Attributes:
        name: Logical template name, e.g. ``"E-PARSE"``.
        version: Numeric version string, e.g. ``"1"``.
        text: The raw template text with ``$name`` placeholders.
    """

    name: str
    version: str
    text: str


def _discover() -> dict[str, PromptTemplate]:
    """Discover all template files in the prompts directory.

    Filenames are expected to be ``{NAME}-v{VERSION}.md``. The highest version
    for each name is kept.

    Returns:
        Mapping from template name to its latest discovered version.
    """
    templates: dict[str, PromptTemplate] = {}
    if not _TEMPLATE_DIR.exists():
        return templates
    for path in sorted(_TEMPLATE_DIR.glob("*.md")):
        match = re.match(r"^(.+)-v(\d+)\.md$", path.name)
        if not match:
            continue
        name, version = match.groups()
        existing = templates.get(name)
        if existing is None or int(version) > int(existing.version):
            templates[name] = PromptTemplate(
                name=name,
                version=version,
                text=path.read_text(encoding="utf-8"),
            )
    return templates


def list_templates() -> Sequence[str]:
    """Return the names of all available prompt templates."""
    return sorted(_discover().keys())


def load_template(name: str) -> PromptTemplate:
    """Load the latest version of a prompt template by name.

    Args:
        name: Template name, e.g. ``"E-PARSE"``.

    Returns:
        The highest-versioned template with that name.

    Raises:
        KeyError: if no template exists for *name*.
    """
    templates = _discover()
    if name not in templates:
        msg = f"Unknown prompt template: {name!r}"
        raise KeyError(msg)
    return templates[name]


def _sanitize_value(value: object, max_length: int) -> object:
    """Recursively sanitize a variable value for prompt injection hardening.

    Strings are stripped of control characters and truncated. Mappings and
    sequences are processed recursively. Other values are returned unchanged.

    Args:
        value: The variable value to sanitize.
        max_length: Maximum string length allowed.

    Returns:
        The sanitized value.
    """
    if isinstance(value, str):
        return truncate(strip_control_chars(value), max_length)
    if isinstance(value, Mapping):
        return {str(k): _sanitize_value(v, max_length) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_sanitize_value(v, max_length) for v in value]
    return value


def _source_text_key(variables: Mapping[str, object]) -> str | None:
    """Return the key that holds the source text for span verification, if any."""
    for key in ("text", "resume_text", "source_text"):
        if key in variables and isinstance(variables[key], str):
            return key
    return None


def render(
    template: PromptTemplate,
    variables: Mapping[str, object],
    *,
    nonce: str,
    quarantined_spans: Sequence[tuple[int, int]] = (),
    max_content_length: int = 200_000,
    schema_json: str | None = None,
) -> tuple[str, str | None]:
    """Render a prompt template with hardened variables.

    The rendered prompt is safe to send to an untrusted LLM endpoint: control
    characters are stripped, content is length-capped, and spans flagged by the
    injection detector are removed. The source text used for span verification
    is returned alongside the rendered prompt.

    Args:
        template: The template to render.
        variables: Values to substitute into the template.
        nonce: Per-run nonce used to delimit content blocks.
        quarantined_spans: Character spans to remove from the source text.
        max_content_length: Maximum length for any string variable.
        schema_json: Optional JSON schema string to include as ``$schema``.

    Returns:
        Tuple of ``(rendered_prompt, source_text)``. *source_text* is the
        sanitized text that response spans will be verified against, or ``None``
        if no source text was supplied.
    """
    sanitized: dict[str, object] = {}
    source_text: str | None = None
    source_key = _source_text_key(variables)

    for key, value in variables.items():
        if key == source_key and isinstance(value, str):
            text = value
            if quarantined_spans:
                text = remove_quarantined_spans(text, quarantined_spans)
            text = strip_control_chars(text)
            text = truncate(text, max_content_length)
            sanitized[key] = text
            source_text = text
        elif key == "quarantined_spans":
            continue
        else:
            sanitized[key] = _sanitize_value(value, max_content_length)

    if schema_json is not None:
        sanitized["schema"] = schema_json
    sanitized["nonce"] = nonce

    t = string.Template(template.text)
    return t.substitute(sanitized), source_text
