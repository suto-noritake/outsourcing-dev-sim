from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

import yaml


_VALID_REASONING_EFFORTS = {
    "none",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
}
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")
_REQUIRED_FIELDS = {"id", "name", "role", "model", "order"}
_KNOWN_FIELDS = {
    "id",
    "name",
    "role",
    "model",
    "order",
    "enabled",
    "reasoning_effort",
    "specialty",
    "depends_on",
    "input_artifacts",
    "output_artifacts",
    "timeout_sec",
    "max_ai_credits",
    "permissions",
}
_KNOWN_PERMISSION_FIELDS = {
    "allow_all_tools",
    "allow_tools",
    "deny_tools",
    "allow_urls",
    "add_dirs",
}
_DEFAULT_DENY_TOOLS = ["shell(git push)"]


@dataclass
class Permissions:
    allow_all_tools: bool = False
    allow_tools: list[str] = field(default_factory=list)
    deny_tools: list[str] = field(default_factory=lambda: _DEFAULT_DENY_TOOLS.copy())
    allow_urls: list[str] = field(default_factory=list)
    add_dirs: list[str] = field(default_factory=list)


@dataclass
class TeamMember:
    id: str
    name: str
    role: str
    model: str
    order: int
    enabled: bool = True
    reasoning_effort: str = "medium"
    specialty: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    input_artifacts: list[str] = field(default_factory=list)
    output_artifacts: list[str] = field(default_factory=list)
    timeout_sec: int = 1800
    max_ai_credits: int | None = None
    permissions: Permissions = field(default_factory=Permissions)
    body: str = ""
    source_path: Path | None = None


@dataclass
class TeamLoadResult:
    members: list[TeamMember]
    warnings: list[str]


class TeamLoadError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(self._format(errors))

    @staticmethod
    def _format(errors: list[str]) -> str:
        rendered = "\n".join(f"- {message}" for message in errors)
        return f"Team load failed with {len(errors)} error(s):\n{rendered}"


def load_team(team_dir: Path) -> TeamLoadResult:
    team_dir = Path(team_dir).resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not team_dir.exists() or not team_dir.is_dir():
        raise TeamLoadError([f"Team directory does not exist: {team_dir}"])

    member_files = [
        path
        for path in sorted(team_dir.glob("*.md"), key=lambda p: p.name.lower())
        if not path.name.startswith("_") and path.name.lower() != "readme.md"
    ]
    if not member_files:
        raise TeamLoadError([f"No member definition files (*.md) found: {team_dir}"])

    members: list[TeamMember] = []
    for member_file in member_files:
        member = _parse_member_file(member_file, errors, warnings)
        if member is not None:
            members.append(member)

    duplicate_errors = _check_duplicate_ids(members)
    errors.extend(duplicate_errors)

    member_by_id = {member.id: member for member in members}
    errors.extend(_validate_dependency_targets(member_by_id))
    errors.extend(_validate_enabled_dependency_constraints(member_by_id))

    if errors:
        raise TeamLoadError(errors)

    try:
        ordered_ids = _resolve_topological_order(member_by_id)
    except TeamLoadError as cycle_error:
        errors.extend(cycle_error.errors)
        raise TeamLoadError(errors) from cycle_error

    enabled_members = [member_by_id[member_id] for member_id in ordered_ids if member_by_id[member_id].enabled]
    return TeamLoadResult(members=enabled_members, warnings=warnings)


def _parse_member_file(path: Path, errors: list[str], warnings: list[str]) -> TeamMember | None:
    file_errors: list[str] = []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{path}: failed to read file ({exc})")
        return None

    frontmatter_raw, body = _extract_frontmatter(path, raw, file_errors)
    if frontmatter_raw is None:
        errors.extend(file_errors)
        return None

    try:
        loaded = yaml.safe_load(frontmatter_raw)
    except yaml.YAMLError as exc:
        file_errors.append(f"{path}: invalid YAML frontmatter ({exc})")
        errors.extend(file_errors)
        return None

    if not isinstance(loaded, dict):
        file_errors.append(f"{path}: frontmatter must be a YAML mapping/object")
        errors.extend(file_errors)
        return None

    frontmatter = dict(loaded)
    member = _build_team_member(path, frontmatter, body, file_errors, warnings)
    errors.extend(file_errors)
    return member


def _extract_frontmatter(path: Path, raw: str, errors: list[str]) -> tuple[str | None, str]:
    content = raw.lstrip("\ufeff")
    lines = content.splitlines(keepends=True)

    if not lines or lines[0].strip() != "---":
        errors.append(f"{path}: missing YAML frontmatter opening delimiter '---'")
        return None, ""

    closing_index: int | None = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            closing_index = idx
            break

    if closing_index is None:
        errors.append(f"{path}: missing YAML frontmatter closing delimiter '---'")
        return None, ""

    frontmatter = "".join(lines[1:closing_index])
    body = "".join(lines[closing_index + 1 :]).strip()
    return frontmatter, body


def _build_team_member(
    path: Path,
    frontmatter: dict[str, Any],
    body: str,
    errors: list[str],
    warnings: list[str],
) -> TeamMember | None:
    for missing_key in sorted(_REQUIRED_FIELDS - set(frontmatter.keys())):
        errors.append(f"{path}: required field '{missing_key}' is missing")

    unknown_keys = sorted(set(frontmatter.keys()) - _KNOWN_FIELDS)
    for key in unknown_keys:
        warnings.append(f"{path}: unknown frontmatter key '{key}'")

    raw_id = frontmatter.get("id")
    raw_name = frontmatter.get("name")
    raw_role = frontmatter.get("role")
    raw_model = frontmatter.get("model")
    raw_order = frontmatter.get("order")

    member_id = _require_nonempty_string(path, "id", raw_id, errors)
    name = _require_nonempty_string(path, "name", raw_name, errors)
    role = _require_nonempty_string(path, "role", raw_role, errors)
    model = _require_nonempty_string(path, "model", raw_model, errors)
    order = _require_int(path, "order", raw_order, errors)

    if member_id is not None and _ID_PATTERN.match(member_id) is None:
        errors.append(
            f"{path}: field 'id' must match pattern '^[a-z][a-z0-9_-]*$' (got: {member_id!r})"
        )

    enabled = _optional_bool(path, "enabled", frontmatter.get("enabled", True), errors, default=True)
    reasoning_effort = _optional_string(
        path, "reasoning_effort", frontmatter.get("reasoning_effort", "medium"), errors, default="medium"
    )
    if reasoning_effort is not None and reasoning_effort not in _VALID_REASONING_EFFORTS:
        errors.append(
            f"{path}: field 'reasoning_effort' must be one of {sorted(_VALID_REASONING_EFFORTS)} "
            f"(got: {reasoning_effort!r})"
        )

    specialty = _optional_str_or_list(path, "specialty", frontmatter.get("specialty", []), errors, default=[])
    depends_on = _optional_string_list(path, "depends_on", frontmatter.get("depends_on", []), errors, default=[])
    input_artifacts = _optional_string_list(
        path,
        "input_artifacts",
        frontmatter.get("input_artifacts", []),
        errors,
        default=[],
    )
    output_artifacts = _optional_string_list(
        path,
        "output_artifacts",
        frontmatter.get("output_artifacts", []),
        errors,
        default=[],
    )
    timeout_sec = _optional_int(path, "timeout_sec", frontmatter.get("timeout_sec", 1800), errors, default=1800)
    if timeout_sec is not None and timeout_sec <= 0:
        errors.append(f"{path}: field 'timeout_sec' must be > 0 (got: {timeout_sec})")

    max_ai_credits = frontmatter.get("max_ai_credits", None)
    parsed_max_ai_credits: int | None
    if max_ai_credits is None:
        parsed_max_ai_credits = None
    elif isinstance(max_ai_credits, bool) or not isinstance(max_ai_credits, int):
        errors.append(f"{path}: field 'max_ai_credits' must be an integer >= 30 or null")
        parsed_max_ai_credits = None
    elif max_ai_credits < 30:
        errors.append(f"{path}: field 'max_ai_credits' must be >= 30 when specified (got: {max_ai_credits})")
        parsed_max_ai_credits = max_ai_credits
    else:
        parsed_max_ai_credits = max_ai_credits

    permissions = _parse_permissions(path, frontmatter.get("permissions", {}), errors, warnings)

    if errors:
        return None

    return TeamMember(
        id=member_id or "",
        name=name or "",
        role=role or "",
        model=model or "",
        order=order or 0,
        enabled=enabled,
        reasoning_effort=reasoning_effort or "medium",
        specialty=specialty,
        depends_on=depends_on,
        input_artifacts=input_artifacts,
        output_artifacts=output_artifacts,
        timeout_sec=timeout_sec or 1800,
        max_ai_credits=parsed_max_ai_credits,
        permissions=permissions,
        body=body,
        source_path=path,
    )


def _parse_permissions(path: Path, value: Any, errors: list[str], warnings: list[str]) -> Permissions:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        errors.append(f"{path}: field 'permissions' must be an object")
        return Permissions()

    unknown_keys = sorted(set(value.keys()) - _KNOWN_PERMISSION_FIELDS)
    for key in unknown_keys:
        warnings.append(f"{path}: unknown permissions key '{key}'")

    allow_all_tools = _optional_bool(
        path,
        "permissions.allow_all_tools",
        value.get("allow_all_tools", False),
        errors,
        default=False,
    )
    allow_tools = _optional_string_list(
        path,
        "permissions.allow_tools",
        value.get("allow_tools", []),
        errors,
        default=[],
    )
    deny_tools = _optional_string_list(
        path,
        "permissions.deny_tools",
        value.get("deny_tools", []),
        errors,
        default=[],
    )
    allow_urls = _optional_string_list(
        path,
        "permissions.allow_urls",
        value.get("allow_urls", []),
        errors,
        default=[],
    )
    add_dirs = _optional_string_list(
        path,
        "permissions.add_dirs",
        value.get("add_dirs", []),
        errors,
        default=[],
    )

    for add_dir in add_dirs:
        if not Path(add_dir).is_absolute():
            errors.append(f"{path}: permissions.add_dirs must contain absolute paths (got: {add_dir!r})")

    merged_deny_tools: list[str] = []
    for deny_tool in [*deny_tools, *_DEFAULT_DENY_TOOLS]:
        if deny_tool not in merged_deny_tools:
            merged_deny_tools.append(deny_tool)

    return Permissions(
        allow_all_tools=allow_all_tools,
        allow_tools=allow_tools,
        deny_tools=merged_deny_tools,
        allow_urls=allow_urls,
        add_dirs=add_dirs,
    )


def _check_duplicate_ids(members: list[TeamMember]) -> list[str]:
    errors: list[str] = []
    paths_by_id: dict[str, list[Path]] = {}
    for member in members:
        if not member.id:
            continue
        paths_by_id.setdefault(member.id, []).append(member.source_path or Path("<unknown>"))

    for member_id, paths in sorted(paths_by_id.items()):
        if len(paths) > 1:
            rendered = ", ".join(str(path) for path in paths)
            errors.append(f"Duplicate member id '{member_id}' found in: {rendered}")
    return errors


def _validate_dependency_targets(member_by_id: dict[str, TeamMember]) -> list[str]:
    errors: list[str] = []
    for member in member_by_id.values():
        for dep_id in member.depends_on:
            if dep_id not in member_by_id:
                source = member.source_path or Path("<unknown>")
                errors.append(
                    f"{source}: depends_on contains unknown member id '{dep_id}' "
                    f"(member: {member.id})"
                )
    return errors


def _validate_enabled_dependency_constraints(member_by_id: dict[str, TeamMember]) -> list[str]:
    errors: list[str] = []
    for member in member_by_id.values():
        if not member.enabled:
            continue
        for dep_id in member.depends_on:
            dep = member_by_id.get(dep_id)
            if dep is not None and not dep.enabled:
                source = member.source_path or Path("<unknown>")
                errors.append(
                    f"{source}: enabled member '{member.id}' depends_on disabled member '{dep_id}'"
                )
    return errors


def _resolve_topological_order(member_by_id: dict[str, TeamMember]) -> list[str]:
    indegree: dict[str, int] = {member_id: len(member.depends_on) for member_id, member in member_by_id.items()}
    outgoing: dict[str, list[str]] = {member_id: [] for member_id in member_by_id}

    for member in member_by_id.values():
        for dep_id in member.depends_on:
            outgoing[dep_id].append(member.id)

    ready = [member_id for member_id, degree in indegree.items() if degree == 0]
    ordered: list[str] = []

    while ready:
        current_layer = sorted(ready, key=lambda member_id: (member_by_id[member_id].order, member_id))
        next_ready: list[str] = []

        for member_id in current_layer:
            ordered.append(member_id)
            for dependent_id in sorted(outgoing[member_id], key=lambda mid: (member_by_id[mid].order, mid)):
                indegree[dependent_id] -= 1
                if indegree[dependent_id] == 0:
                    next_ready.append(dependent_id)
        ready = next_ready

    if len(ordered) != len(member_by_id):
        cycle_members = sorted(member_id for member_id, degree in indegree.items() if degree > 0)
        raise TeamLoadError(
            [f"Cycle detected in depends_on graph. Members involved: {', '.join(cycle_members)}"]
        )
    return ordered


def _require_nonempty_string(path: Path, field_name: str, value: Any, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}: field '{field_name}' must be a non-empty string")
        return None
    return value.strip()


def _require_int(path: Path, field_name: str, value: Any, errors: list[str]) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{path}: field '{field_name}' must be an integer")
        return None
    return value


def _optional_bool(path: Path, field_name: str, value: Any, errors: list[str], *, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        errors.append(f"{path}: field '{field_name}' must be a boolean")
        return default
    return value


def _optional_string(path: Path, field_name: str, value: Any, errors: list[str], *, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path}: field '{field_name}' must be a non-empty string")
        return default
    return value.strip()


def _optional_int(path: Path, field_name: str, value: Any, errors: list[str], *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{path}: field '{field_name}' must be an integer")
        return default
    return value


def _optional_string_list(
    path: Path, field_name: str, value: Any, errors: list[str], *, default: list[str]
) -> list[str]:
    if value is None:
        return list(default)
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        errors.append(f"{path}: field '{field_name}' must be a string or list of strings")
        return list(default)

    normalized: list[str] = []
    for idx, item in enumerate(values):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{path}: field '{field_name}[{idx}]' must be a non-empty string")
            continue
        normalized.append(item.strip())
    return normalized


def _optional_str_or_list(
    path: Path, field_name: str, value: Any, errors: list[str], *, default: list[str]
) -> list[str]:
    if value is None:
        return list(default)
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            errors.append(f"{path}: field '{field_name}' must not be empty when string")
            return list(default)
        return [normalized]
    if isinstance(value, list):
        return _optional_string_list(path, field_name, value, errors, default=default)

    errors.append(f"{path}: field '{field_name}' must be a string or list of strings")
    return list(default)
