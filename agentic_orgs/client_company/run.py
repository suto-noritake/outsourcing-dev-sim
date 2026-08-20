from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import sys
import uuid

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agentic_orgs.client_company.persona_mapping import assess_persona
from agentic_orgs.common.copilot_cli import invoke_copilot_member, member_invocation_result_to_json
from agentic_orgs.common.team_loader import TeamLoadError, load_team
from outsourcing_sim.params import SimParams


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    team_dir = Path(args.team_dir).resolve()
    workspace_dir = Path(args.workspace_dir).resolve()
    case_id = args.case_id
    run_id = _build_run_id()
    run_log_dir = REPO_ROOT / "agentic_orgs" / "logs" / "runs" / "client_company" / case_id / run_id
    artifacts_dir = run_log_dir / "artifacts"
    run_log_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    if not workspace_dir.exists() or not workspace_dir.is_dir():
        raise SystemExit(f"--workspace-dir does not exist: {workspace_dir}")

    try:
        team_result = load_team(team_dir)
    except TeamLoadError as exc:
        print(exc, file=sys.stderr)
        return 1

    abm_payload = {
        "funds_0": args.funds,
        "budget_c0": args.budget_c0,
        "budget_c1": args.budget_c1,
        "difficulty_0": args.difficulty0,
        "k1": args.k1,
        "gamma": args.gamma,
        "alpha": args.alpha,
        "partial_pay": args.partial_pay,
        "r_min": args.r_min,
        "max_consecutive_failures": args.max_consecutive_failures,
    }
    persona = assess_persona(
        gamma=args.gamma,
        difficulty_0=args.difficulty0,
        budget_c0=args.budget_c0,
        budget_c1=args.budget_c1,
        partial_pay=args.partial_pay,
        r_min=args.r_min,
        max_consecutive_failures=args.max_consecutive_failures,
    )
    persona_payload = asdict(persona)

    context_path = artifacts_dir / "client_persona_context.json"
    context_payload = {
        "case_id": case_id,
        "task_theme": args.task_theme,
        "abm_parameters": abm_payload,
        "persona_assessment": persona_payload,
        "defaults_reference": SimParams().to_dict(),
    }
    context_path.write_text(json.dumps(context_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    member_results = []
    status = "success"
    for member in team_result.members:
        prompt = _build_member_prompt(
            member_body=member.body,
            member_id=member.id,
            task_theme=args.task_theme,
            context_path=context_path,
            artifacts_dir=artifacts_dir,
            templates_dir=Path(args.templates_dir).resolve(),
            output_artifacts=member.output_artifacts,
        )
        result = invoke_copilot_member(
            member=member,
            prompt=prompt,
            workspace_dir=workspace_dir,
            run_log_dir=run_log_dir,
            run_name_prefix=f"client-{case_id}-{run_id}",
        )
        member_results.append(member_invocation_result_to_json(result))
        if not result.success:
            status = "failed"
            break

    manifest_path = run_log_dir / "manifest.json"
    manifest = {
        "company": "client_company",
        "case_id": case_id,
        "run_id": run_id,
        "status": status,
        "workspace_dir": str(workspace_dir),
        "team_dir": str(team_dir),
        "templates_dir": str(Path(args.templates_dir).resolve()),
        "created_at": datetime.now().isoformat(),
        "warnings": team_result.warnings,
        "context_path": str(context_path),
        "member_results": member_results,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if status != "success":
        print(f"[client_company] failed. see: {run_log_dir}", file=sys.stderr)
        return 1

    print(f"[client_company] success. run_log_dir={run_log_dir}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    defaults = SimParams()
    parser = argparse.ArgumentParser(description="Run client_company request generation pipeline.")
    parser.add_argument("--case-id", default="default", help="Case identifier.")
    parser.add_argument("--workspace-dir", default=str(REPO_ROOT), help="Target workspace path for Copilot -C.")
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
    parser.add_argument("--task-theme", default="シンプルなCLI電卓を作って", help="Project brief text.")

    parser.add_argument("--funds", type=float, default=defaults.funds_0, help="ABM funds_0 reference value.")
    parser.add_argument("--budget-c0", type=float, default=defaults.budget_c0)
    parser.add_argument("--budget-c1", type=float, default=defaults.budget_c1)
    parser.add_argument("--difficulty0", type=float, default=defaults.difficulty_0)
    parser.add_argument("--k1", type=float, default=defaults.k1)
    parser.add_argument("--gamma", type=float, default=defaults.gamma)
    parser.add_argument("--alpha", type=float, default=defaults.alpha)
    parser.add_argument("--partial-pay", type=float, default=defaults.partial_pay)
    parser.add_argument("--r-min", type=float, default=defaults.r_min)
    parser.add_argument("--max-consecutive-failures", type=int, default=defaults.max_consecutive_failures)
    return parser


def _build_member_prompt(
    *,
    member_body: str,
    member_id: str,
    task_theme: str,
    context_path: Path,
    artifacts_dir: Path,
    templates_dir: Path,
    output_artifacts: list[str],
) -> str:
    template_paths = sorted(templates_dir.glob("*.md"))
    rendered_templates = "\n".join(f"- {path}" for path in template_paths) if template_paths else "- (なし)"
    rendered_outputs = "\n".join(f"- {artifacts_dir / name}" for name in output_artifacts) or "- (出力指定なし)"

    return f"""あなたは client_company の {member_id} です。以下の人格ポリシーに従ってください。

## 人格ポリシー
{member_body}

## 実行指示
1. まず次のコンテキストJSONを読むこと: {context_path}
2. テーマ: {task_theme}
3. 次のテンプレートを参照して、委託要求書を作成すること:
{rendered_templates}
4. 生成物は必ず次の絶対パスへ保存すること（UTF-8）:
{rendered_outputs}
5. 出力ファイル本文には、要件・制約・受け入れ基準・優先順位を明確に記述すること。
6. 最終回答では、作成したファイル一覧と要点を簡潔に報告すること。
"""


def _build_run_id() -> str:
    now = datetime.now()
    suffix = uuid.uuid4().hex[:6]
    return f"run_{now:%Y%m%d-%H%M%S}_{suffix}"


if __name__ == "__main__":
    raise SystemExit(main())

