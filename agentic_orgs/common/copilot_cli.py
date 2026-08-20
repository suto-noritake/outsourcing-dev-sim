from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import uuid

from .team_loader import TeamMember


@dataclass
class MemberInvocationResult:
    member_id: str
    exit_code: int | None
    timed_out: bool
    session_id: str | None
    stdout_path: Path
    stderr_path: Path
    meta_path: Path
    started_at: datetime
    ended_at: datetime
    duration_sec: float
    success: bool
    result_exit_code: int | None = None
    parse_warnings: list[str] = field(default_factory=list)
    missing_artifacts: list[str] = field(default_factory=list)
    command: list[str] = field(default_factory=list)


def invoke_copilot_member(
    member: TeamMember,
    prompt: str,
    *,
    workspace_dir: Path,
    run_log_dir: Path,
    run_name_prefix: str,
) -> MemberInvocationResult:
    workspace_dir = Path(workspace_dir).resolve()
    run_log_dir = Path(run_log_dir).resolve()
    artifacts_dir = run_log_dir / "artifacts"
    prompts_dir = run_log_dir / "_prompts"
    internal_log_dir = run_log_dir / "_copilot_internal" / member.id

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    internal_log_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = prompts_dir / f"{member.id}_{uuid.uuid4().hex}.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    dispatch_prompt = (
        "最初に次のUTF-8ファイルを読み、記載された指示をそのまま実行してください。"
        f" 指示ファイル: {prompt_path}"
    )

    session_name = run_name_prefix if run_name_prefix.endswith(member.id) else f"{run_name_prefix}-{member.id}"
    command = _build_command(
        member=member,
        dispatch_prompt=dispatch_prompt,
        workspace_dir=workspace_dir,
        run_log_dir=run_log_dir,
        internal_log_dir=internal_log_dir,
        session_name=session_name,
    )

    stdout_path = run_log_dir / f"{member.id}.stdout.log"
    stderr_path = run_log_dir / f"{member.id}.stderr.log"
    meta_path = run_log_dir / f"{member.id}.meta.json"

    started_at = datetime.now(timezone.utc)
    timed_out = False
    exit_code: int | None = None
    stdout_text = ""
    stderr_text = ""
    timeout_error: str | None = None

    try:
        completed = subprocess.run(
            command,
            cwd=str(workspace_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=member.timeout_sec,
            check=False,
            env=_build_child_env(),
        )
        exit_code = completed.returncode
        stdout_text = completed.stdout or ""
        stderr_text = completed.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout_text = exc.stdout or ""
        stderr_text = exc.stderr or ""
        timeout_error = f"Command timed out after {member.timeout_sec} sec"

    ended_at = datetime.now(timezone.utc)
    duration_sec = (ended_at - started_at).total_seconds()

    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")

    parse_warnings, result_event_exit_code, session_id = _parse_jsonl(stdout_text)
    if timeout_error is not None:
        parse_warnings.append(timeout_error)

    missing_artifacts = _missing_output_artifacts(member, artifacts_dir)
    success = (
        exit_code == 0
        and not timed_out
        and result_event_exit_code == 0
        and len(missing_artifacts) == 0
    )

    meta = {
        "member_id": member.id,
        "member_name": member.name,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "duration_sec": duration_sec,
        "workspace_dir": str(workspace_dir),
        "run_log_dir": str(run_log_dir),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "prompt_path": str(prompt_path),
        "command": command,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "result_exit_code": result_event_exit_code,
        "session_id": session_id,
        "missing_artifacts": missing_artifacts,
        "parse_warnings": parse_warnings,
        "success": success,
        "model": member.model,
        "reasoning_effort": member.reasoning_effort,
        "max_ai_credits": member.max_ai_credits,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return MemberInvocationResult(
        member_id=member.id,
        exit_code=exit_code,
        timed_out=timed_out,
        session_id=session_id,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        meta_path=meta_path,
        started_at=started_at,
        ended_at=ended_at,
        duration_sec=duration_sec,
        success=success,
        result_exit_code=result_event_exit_code,
        parse_warnings=parse_warnings,
        missing_artifacts=missing_artifacts,
        command=command,
    )


def member_invocation_result_to_json(result: MemberInvocationResult) -> dict:
    data = asdict(result)
    data["stdout_path"] = str(result.stdout_path)
    data["stderr_path"] = str(result.stderr_path)
    data["meta_path"] = str(result.meta_path)
    data["started_at"] = result.started_at.isoformat()
    data["ended_at"] = result.ended_at.isoformat()
    return data


def _build_command(
    *,
    member: TeamMember,
    dispatch_prompt: str,
    workspace_dir: Path,
    run_log_dir: Path,
    internal_log_dir: Path,
    session_name: str,
) -> list[str]:
    command = [
        "copilot",
        "-p",
        dispatch_prompt,
        "--output-format",
        "json",
        "--no-color",
        "--no-custom-instructions",
        "--disable-builtin-mcps",
        "--no-remote",
        "--no-remote-export",
        "-C",
        str(workspace_dir),
        "--add-dir",
        str(run_log_dir),
        "--model",
        member.model,
        "--effort",
        member.reasoning_effort,
        "-n",
        session_name,
        "--log-dir",
        str(internal_log_dir),
    ]

    if member.max_ai_credits is not None:
        command.extend(["--max-ai-credits", str(member.max_ai_credits)])

    if member.permissions.allow_all_tools:
        command.append("--allow-all-tools")

    for tool in member.permissions.allow_tools:
        command.append(f"--allow-tool={tool}")
    for tool in member.permissions.deny_tools:
        command.append(f"--deny-tool={tool}")
    for url in member.permissions.allow_urls:
        command.append(f"--allow-url={url}")
    for add_dir in member.permissions.add_dirs:
        command.extend(["--add-dir", add_dir])

    return command


def _parse_jsonl(stdout_text: str) -> tuple[list[str], int | None, str | None]:
    warnings: list[str] = []
    result_exit_code: int | None = None
    session_id: str | None = None

    for line_number, raw_line in enumerate(stdout_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            warnings.append(f"stdout line {line_number}: JSON parse failed ({exc})")
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "result":
            if "exitCode" in event:
                result_exit_code = event.get("exitCode")
            if "sessionId" in event:
                session_id = event.get("sessionId")

    return warnings, result_exit_code, session_id


def _missing_output_artifacts(member: TeamMember, artifacts_dir: Path) -> list[str]:
    missing: list[str] = []
    for artifact_name in member.output_artifacts:
        artifact_path = artifacts_dir / artifact_name
        if not artifact_path.exists():
            missing.append(str(artifact_path))
    return missing


def _build_child_env() -> dict[str, str]:
    keep_exact = {
        "APPDATA",
        "COMSPEC",
        "HOME",
        "HOMEDRIVE",
        "HOMEPATH",
        "LOCALAPPDATA",
        "OS",
        "PATH",
        "PATHEXT",
        "PROGRAMDATA",
        "SYSTEMDRIVE",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "WINDIR",
    }
    keep_prefixes = (
        "COPILOT_",
        "GITHUB_",
        "HTTP_",
        "HTTPS_",
        "NO_PROXY",
    )
    child_env: dict[str, str] = {}
    for key, value in os.environ.items():
        key_upper = key.upper()
        if key_upper in keep_exact or key_upper.startswith(keep_prefixes):
            child_env[key] = value
    child_env["PYTHONUTF8"] = "1"
    return child_env

