"""Small, validated public contracts. No model provider is needed to import these."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import json
import math
import re
from typing import Any


def _text(value: Any, field: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise ValueError(f"{field} must be {'a' if empty else 'a non-empty'} string")
    return value


@dataclass(frozen=True)
class Fragment:
    id: str
    text: str

    def __post_init__(self) -> None:
        _text(self.id, "fragment.id")
        _text(self.text, "fragment.text")


def parse_fragments(value: Any, *, field: str = "before") -> tuple[Fragment, ...]:
    if isinstance(value, str):
        parts = [part for part in re.split(r"\r?\n[ \t]*\r?\n(?:[ \t]*\r?\n)*", value) if part.strip()]
        fragments = tuple(Fragment(f"f{i:03d}", part) for i, part in enumerate(parts, 1))
    elif isinstance(value, (list, tuple)):
        parsed = []
        for item in value:
            if isinstance(item, Fragment):
                parsed.append(item)
            elif isinstance(item, dict) and set(item) == {"id", "text"}:
                parsed.append(Fragment(item["id"], item["text"]))
            else:
                raise ValueError(f"{field} entries must contain exactly id and text")
        fragments = tuple(parsed)
    else:
        raise ValueError(f"{field} must be a string or fragment list")
    if len({fragment.id for fragment in fragments}) != len(fragments):
        raise ValueError(f"{field} fragment ids must be unique")
    return fragments


def _finite_json(value: Any) -> bool:
    if value is None or type(value) in (bool, int, str):
        return True
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is list:
        return all(_finite_json(item) for item in value)
    if type(value) is dict:
        return all(isinstance(key, str) and _finite_json(item) for key, item in value.items())
    return False


def validate_evaluator(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("evaluator must be an object")
    kind = value.get("type")
    if kind == "contains":
        if set(value) - {"type", "all", "none"}:
            raise ValueError("unknown contains evaluator field")
        required, forbidden = value.get("all", []), value.get("none", [])
        for entries in (required, forbidden):
            if not isinstance(entries, list) or not all(isinstance(v, str) and v for v in entries):
                raise ValueError("contains all/none must be lists of non-empty strings")
        if not required and not forbidden:
            raise ValueError("contains evaluator needs at least one assertion")
        if set(required) & set(forbidden):
            raise ValueError("a contains assertion cannot be both required and forbidden")
    elif kind in {"exact", "json"}:
        if set(value) != {"type", "expected"}:
            raise ValueError(f"{kind} evaluator requires exactly type and expected")
        if kind == "exact":
            _text(value["expected"], "evaluator.expected", empty=True)
        elif not _finite_json(value["expected"]):
            raise ValueError("json expected must be a finite JSON value")
    else:
        raise ValueError("evaluator.type must be contains, exact, or json")
    return deepcopy(value)


@dataclass(frozen=True)
class Case:
    name: str
    before: tuple[Fragment, ...]
    after: str
    task: str
    evaluator: dict[str, Any]
    _original_text: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        _text(self.name, "name")
        if isinstance(self.before, str):
            object.__setattr__(self, "_original_text", self.before)
        fragments = parse_fragments(self.before)
        if not fragments:
            raise ValueError("before must contain at least one non-empty fragment")
        object.__setattr__(self, "before", fragments)
        if self._original_text is not None:
            _text(self._original_text, "original context")
            if parse_fragments(self._original_text) != fragments:
                raise ValueError("original text must match parsed before fragments")
        _text(self.after, "after", empty=True)
        _text(self.task, "task")
        object.__setattr__(self, "evaluator", validate_evaluator(self.evaluator))

    @property
    def original_context(self) -> str:
        return self._original_text if self._original_text is not None else "\n\n".join(fragment.text for fragment in self.before)

    @classmethod
    def from_dict(cls, data: Any) -> Case:
        if not isinstance(data, dict):
            raise ValueError("case must be a JSON object")
        required = {"version", "name", "before", "after", "task", "evaluator"}
        if set(data) != required:
            raise ValueError("case requires exactly version, name, before, after, task, evaluator")
        if type(data["version"]) is not int or data["version"] != 1:
            raise ValueError("only case version 1 is supported")
        before = parse_fragments(data["before"])
        after = data["after"]
        if not isinstance(after, str):
            after = "\n\n".join(f.text for f in parse_fragments(after, field="after"))
        return cls(data["name"], before, after, data["task"], data["evaluator"], data["before"] if isinstance(data["before"], str) else None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1, "name": self.name,
            "before": self._original_text if self._original_text is not None else [{"id": f.id, "text": f.text} for f in self.before],
            "after": self.after, "task": self.task, "evaluator": deepcopy(self.evaluator),
        }


@dataclass(frozen=True)
class Response:
    output: str
    usage: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        _text(self.output, "response.output", empty=True)
        if self.usage is not None and (not isinstance(self.usage, dict) or not _finite_json(self.usage)):
            raise ValueError("response.usage must be a finite JSON object or None")


def _strict_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_strict_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(_strict_equal(a, b) for a, b in zip(left, right))
    return left == right


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def evaluate(output: str, evaluator: dict[str, Any]) -> bool:
    """Deterministic, deliberately explicit scoring (not an LLM judge)."""
    kind = evaluator["type"]
    if kind == "exact":
        return output.strip() == evaluator["expected"].strip()
    if kind == "contains":
        return all(s in output for s in evaluator.get("all", [])) and not any(
            s in output for s in evaluator.get("none", [])
        )
    try:
        value = json.loads(output, object_pairs_hook=_unique_object)
    except (ValueError, RecursionError):
        return False
    return _finite_json(value) and _strict_equal(value, evaluator["expected"])
