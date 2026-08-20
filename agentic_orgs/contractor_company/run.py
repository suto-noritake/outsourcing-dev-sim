from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import sys
import uuid

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agentic_orgs.common.copilot_cli import invoke_copilot_member, member_invocation_result_to_json
from agentic_orgs.common.team_loader import TeamLoadError, TeamMember, load_team


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    request_file = Path(args.request_file).resolve()
    workspace_dir = Path(args.workspace_dir).resolve()
    team_dir = Path(args.team_dir).resolve()
    templates_dir = Path(args.templates_dir).resolve()

    if not request_file.exists() or not request_file.is_file():
        raise SystemExit(f"--request-file does not exist: {request_file}")
    if not workspace_dir.exists() or not workspace_dir.is_dir():
        raise SystemExit(f"--workspace-dir does not exist: {workspace_dir}")

    case_id = args.case_id
    run_id = _build_run_id()
    run_log_dir = REPO_ROOT / "agentic_orgs" / "logs" / "runs" / "contractor_company" / case_id / run_id
    artifacts_dir = run_log_dir / "artifacts"
    run_log_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    archived_request = artifacts_dir / "request_brief.md"
    shutil.copy2(request_file, archived_request)
    _copy_if_exists(request_file.parent / "acceptance_criteria.md", artifacts_dir / "acceptance_criteria.md")

    try:
        team_result = load_team(team_dir)
    except TeamLoadError as exc:
        print(exc, file=sys.stderr)
        return 1

    results: list[dict] = []
    status = "success"
    for member in team_result.members:
        missing_inputs = _find_missing_inputs(member, artifacts_dir)
        if missing_inputs:
            status = "failed"
            failure = {
                "member_id": member.id,
                "success": False,
                "reason": "missing_input_artifacts",
                "missing_inputs": missing_inputs,
            }
            results.append(failure)
            break

        prompt = _build_member_prompt(
            member=member,
            request_brief_path=archived_request,
            artifacts_dir=artifacts_dir,
            templates_dir=templates_dir,
            workspace_dir=workspace_dir,
        )
        invocation = invoke_copilot_member(
            member=member,
            prompt=prompt,
            workspace_dir=workspace_dir,
            run_log_dir=run_log_dir,
            run_name_prefix=f"contractor-{case_id}-{run_id}",
        )
        results.append(member_invocation_result_to_json(invocation))
        if not invocation.success:
            status = "failed"
            break
        if args.until and member.id == args.until:
            status = "partial_success_until_member"
            break

    summary_path = run_log_dir / "delivery_summary.md"
    summary_path.write_text(_build_delivery_summary(case_id, run_id, status, results), encoding="utf-8")

    manifest = {
        "company": "contractor_company",
        "case_id": case_id,
        "run_id": run_id,
        "status": status,
        "workspace_dir": str(workspace_dir),
        "team_dir": str(team_dir),
        "templates_dir": str(templates_dir),
        "request_brief": str(archived_request),
        "created_at": datetime.now().isoformat(),
        "warnings": team_result.warnings,
        "member_results": results,
        "delivery_summary": str(summary_path),
    }
    manifest_path = run_log_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if status in {"success", "partial_success_until_member"}:
        print(f"[contractor_company] {status}. run_log_dir={run_log_dir}")
        return 0

    print(f"[contractor_company] failed. see: {run_log_dir}", file=sys.stderr)
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run contractor_company delivery pipeline.")
    parser.add_argument("--request-file", required=True, help="Path to client request_brief.md.")
    parser.add_argument("--workspace-dir", required=True, help="Target workspace path for implementation.")
    parser.add_argument("--case-id", default="default", help="Case identifier.")
    parser.add_argument(
        "--team-dir",
        default=str(Path(__file__).resolve().parent / "team"),
        help="Directory containing team member markdown files.",
    )
    parser.add_argument(
        "--templates-dir",
        default=str(Path(__file__).resolve().parent / "templates"),
        help="Directory containing templates.",
    )
    parser.add_argument("--until", default=None, help="Stop after this member ID completes.")
    return parser


def _find_missing_inputs(member: TeamMember, artifacts_dir: Path) -> list[str]:
    missing = []
    for artifact_name in member.input_artifacts:
        path = artifacts_dir / artifact_name
        if not path.exists():
            missing.append(str(path))
    return missing


def _build_member_prompt(
    *,
    member: TeamMember,
    request_brief_path: Path,
    artifacts_dir: Path,
    templates_dir: Path,
    workspace_dir: Path,
) -> str:
    input_lines = "\n".join(f"- {artifacts_dir / artifact}" for artifact in member.input_artifacts) or "- (なし)"
    output_lines = "\n".join(f"- {artifacts_dir / artifact}" for artifact in member.output_artifacts) or "- (なし)"
    template_lines = "\n".join(f"- {path}" for path in sorted(templates_dir.glob("*.md"))) or "- (なし)"

    return f"""あなたは contractor_company の {member.name}（id: {member.id}）です。

## 役割ポリシー
{member.body}

## 共通制約
- 対象ワークスペース: {workspace_dir}
- 要求書（必読）: {request_brief_path}
- 既存成果物（必要に応じて読むこと）:
{input_lines}
- 参照テンプレート:
{template_lines}
- 今回あなたが作成すべき成果物（UTF-8で保存）:
{output_lines}

## 実行指示
1. 先に要求書と入力成果物を確認する。
2. 自分のロールとして必要な判断・作業のみ実行する。
3. 指定された成果物を必ずファイルとして保存する。
4. 最終回答では、作成したファイルパス一覧と要約を報告する。
"""


def _build_delivery_summary(case_id: str, run_id: str, status: str, results: list[dict]) -> str:
    lines = [
        "# delivery_summary",
        "",
        f"- case_id: {case_id}",
        f"- run_id: {run_id}",
        f"- status: {status}",
        "",
        "## member results",
    ]
    for item in results:
        lines.append(
            f"- {item.get('member_id', 'unknown')}: success={item.get('success')} "
            f"exit_code={item.get('exit_code')} timed_out={item.get('timed_out')}"
        )
    return "\n".join(lines) + "\n"


def _copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists() and src.is_file():
        shutil.copy2(src, dst)


def _build_run_id() -> str:
    now = datetime.now()
    suffix = uuid.uuid4().hex[:6]
    return f"run_{now:%Y%m%d-%H%M%S}_{suffix}"


if __name__ == "__main__":
    raise SystemExit(main())
