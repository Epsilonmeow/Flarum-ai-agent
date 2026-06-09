"""
Flarum AI Agent 沙盒测试 Runner

默认特性：
- 使用 MockProvider 离线测试，不调用真实 LLM API
- 使用 data/sandbox/memory 和 data/sandbox/affection，不污染正式记忆
- 不调用 Flarum post_reply，不向真实论坛发帖
- 默认测试结束清理沙盒 memory/affection，仅保留 reports
"""

import argparse
import asyncio
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from core.llm_engine_v2 import LLMEngineV2
from core.providers.manager import ProviderManager
from core.providers.mock_provider import MockProvider


BASE_DIR = Path(__file__).parent
DEFAULT_CASES_PATH = BASE_DIR / "tests" / "sandbox_cases.json"
DEFAULT_SANDBOX_DIR = BASE_DIR / "data" / "sandbox"


def build_mock_engine(sandbox_dir: Path) -> LLMEngineV2:
    """构建使用 MockProvider 和沙盒存储目录的 V2 引擎"""
    manager = ProviderManager()
    manager.register_provider(
        "mock",
        MockProvider(),
        is_primary=True
    )

    return LLMEngineV2(
        provider_manager=manager,
        memory_storage_dir=sandbox_dir / "memory",
        affection_storage_dir=sandbox_dir / "affection"
    )


def load_cases(cases_path: Path, case_filter: str = None) -> List[Dict[str, Any]]:
    """加载测试集"""
    with open(cases_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    if case_filter:
        cases = [case for case in cases if case.get("id") == case_filter]

    if not cases:
        raise ValueError(f"没有找到可运行的测试用例: {case_filter or cases_path}")

    return cases


def ensure_sandbox_dirs(sandbox_dir: Path):
    """创建沙盒目录"""
    (sandbox_dir / "memory").mkdir(parents=True, exist_ok=True)
    (sandbox_dir / "affection").mkdir(parents=True, exist_ok=True)
    (sandbox_dir / "reports").mkdir(parents=True, exist_ok=True)


def cleanup_sandbox_data(sandbox_dir: Path):
    """清理沙盒运行数据，但保留 reports"""
    for subdir in ["memory", "affection"]:
        path = sandbox_dir / subdir
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)


def check_expectations(case: Dict[str, Any], replies: List[str], profile: Dict[str, Any]) -> Dict[str, Any]:
    """根据 case.expect 进行简单断言"""
    expect = case.get("expect", {})
    checks = []

    memory_turns = profile.get("memory", {}).get("total_turns", 0)
    memory_turns_min = expect.get("memory_turns_min")
    if memory_turns_min is not None:
        checks.append({
            "name": "memory_turns_min",
            "passed": memory_turns >= memory_turns_min,
            "actual": memory_turns,
            "expected": memory_turns_min
        })

    affection_score = profile.get("affection", {}).get("score", 0)
    affection_score_min = expect.get("affection_score_min")
    if affection_score_min is not None:
        checks.append({
            "name": "affection_score_min",
            "passed": affection_score >= affection_score_min,
            "actual": affection_score,
            "expected": affection_score_min
        })

    should_contain_any = expect.get("reply_should_contain_any", [])
    if should_contain_any:
        combined_reply = "\n".join(replies)
        matched = [word for word in should_contain_any if word in combined_reply]
        checks.append({
            "name": "reply_should_contain_any",
            "passed": bool(matched),
            "actual": matched,
            "expected": should_contain_any
        })

    return {
        "passed": all(check["passed"] for check in checks),
        "checks": checks
    }


async def run_case(engine: LLMEngineV2, case: Dict[str, Any]) -> Dict[str, Any]:
    """运行单个测试用例"""
    user_id = case["user_id"]
    replies = []
    turns = []

    for message in case.get("messages", []):
        result = await engine.generate(
            user_id=user_id,
            user_message=message,
            temperature=0.7,
            max_tokens=500,
            save_memory=True
        )
        reply = result["reply"]
        replies.append(reply)
        turns.append({
            "user": message,
            "assistant": reply,
            "provider": result.get("provider"),
            "model": result.get("model"),
            "memory_saved": result.get("context", {}).get("memory_saved")
        })

    profile = await engine.get_user_memory_stats(user_id)
    expectation_result = check_expectations(case, replies, profile)

    return {
        "id": case.get("id"),
        "description": case.get("description", ""),
        "user_id": user_id,
        "passed": expectation_result["passed"],
        "checks": expectation_result["checks"],
        "turns": turns,
        "profile": profile
    }


def save_report(sandbox_dir: Path, report: Dict[str, Any]) -> Path:
    """保存测试报告"""
    report_dir = sandbox_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"sandbox_report_{timestamp}.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    return report_path


async def main():
    parser = argparse.ArgumentParser(description="Flarum AI Agent 沙盒测试 Runner")
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH), help="测试集 JSON 路径")
    parser.add_argument("--case", default=None, help="只运行指定 case id")
    parser.add_argument("--sandbox-dir", default=str(DEFAULT_SANDBOX_DIR), help="沙盒数据目录")
    parser.add_argument("--keep-data", action="store_true", help="测试结束后保留沙盒 memory/affection 数据")
    parser.add_argument("--no-clean-before", action="store_true", help="测试前不清理历史沙盒数据")
    args = parser.parse_args()

    sandbox_dir = Path(args.sandbox_dir)
    cases_path = Path(args.cases)

    ensure_sandbox_dirs(sandbox_dir)
    if not args.no_clean_before:
        cleanup_sandbox_data(sandbox_dir)

    cases = load_cases(cases_path, args.case)
    engine = build_mock_engine(sandbox_dir)

    print("=" * 60)
    print("Flarum AI Agent 沙盒测试")
    print("=" * 60)
    print(f"测试集: {cases_path}")
    print(f"沙盒目录: {sandbox_dir}")
    print("Provider: MockProvider（离线，不调用真实 API）")
    print("Flarum: 禁用（不会发帖）")
    print("=" * 60)

    results = []
    for case in cases:
        print(f"\n▶ 运行 case: {case.get('id')} - {case.get('description', '')}")
        result = await run_case(engine, case)
        results.append(result)
        print("  结果:", "✅ PASS" if result["passed"] else "❌ FAIL")
        for check in result["checks"]:
            print(f"   - {check['name']}: {'✅' if check['passed'] else '❌'} actual={check['actual']} expected={check['expected']}")

    report = {
        "generated_at": datetime.now().isoformat(),
        "sandbox_dir": str(sandbox_dir),
        "provider": "mock",
        "flarum_posting": False,
        "total_cases": len(results),
        "passed_cases": sum(1 for r in results if r["passed"]),
        "failed_cases": sum(1 for r in results if not r["passed"]),
        "results": results
    }

    report_path = save_report(sandbox_dir, report)

    if not args.keep_data:
        cleanup_sandbox_data(sandbox_dir)
        cleanup_note = "已清理沙盒 memory/affection，仅保留报告"
    else:
        cleanup_note = "已保留沙盒 memory/affection 数据"

    print("\n" + "=" * 60)
    print(f"总用例: {report['total_cases']} | 通过: {report['passed_cases']} | 失败: {report['failed_cases']}")
    print(f"报告: {report_path}")
    print(cleanup_note)
    print("=" * 60)

    if report["failed_cases"] > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
