#!/usr/bin/env python3
"""
售前智能体 · 检查智能体 (Checker Agent)
职责：内容检查 + 校审技能（术语统一/标题层级/排版风格/编号体系/图表引用格式化）
用法：
  python3 checker.py check <project> <task_id>        # 检查单个任务产出
  python3 checker.py check-all <project> <phase>      # 检查某阶段所有已完成任务
  python3 checker.py report <project> <check_id>      # 查看检查报告
  python3 checker.py override <project> <check_id>    # 人工干预通过
"""
import json, os, sys, glob, posixpath
from datetime import datetime

NFS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "nfs-data")

def _read_json(path):
    if not os.path.exists(path): return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return None

def _write_json(path, data):
    os.makedirs(posixpath.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_artifact(project, rel_path):
    full = os.path.join(NFS_ROOT, "projects", project, rel_path)
    if os.path.isfile(full):
        with open(full, "r", encoding="utf-8") as f:
            return f.read()
    return None


# ===== 检查规则 =====

CONTENT_RULES = [
    {"id": "C01", "name": "内容完整性", "check": lambda text: len(text) > 200,
     "desc": "内容是否足够详实（>200字符）"},
    {"id": "C02", "name": "需求覆盖", "check": lambda text: any(kw in text for kw in ["需求", "功能", "性能"]),
     "desc": "是否覆盖核心需求（需求/功能/性能关键词）"},
    {"id": "C03", "name": "结论清晰", "check": lambda text: any(kw in text for kw in ["总结", "结论", "建议", "方案"]),
     "desc": "是否有明确结论或建议"},
    {"id": "C04", "name": "结构完整", "check": lambda text: text.count("\n## ") >= 1,
     "desc": "是否有二级标题分段"},
]

PROOFREAD_RULES = [
    {"id": "P01", "name": "标题层级", "check": lambda text: text.count("# ") <= 1,
     "desc": "一级标题(#)不应超过1个"},
    {"id": "P02", "name": "编号体系", "check": lambda text: bool(text.strip()),
     "desc": "章节编号是否完整（存根检查）"},
    {"id": "P03", "name": "术语一致性", "check": lambda text: True,
     "desc": "术语用词是否一致（存根检查）"},
    {"id": "P04", "name": "图表引用", "check": lambda text: any(kw in text for kw in ["图", "表", "mermaid", "drawio"]),
     "desc": "是否含图形/表格引用"},
    {"id": "P05", "name": "排版规范", "check": lambda text: all(c not in text for c in ["\t", "  \n"]),
     "desc": "无制表符、无多余空格换行"},
]


def run_content_check(text, task_type):
    """内容检查"""
    results = []
    for rule in CONTENT_RULES:
        passed = rule["check"](text)
        results.append({
            "rule_id": rule["id"],
            "rule_name": rule["name"],
            "status": "pass" if passed else "fail",
            "description": rule["desc"],
        })
    return results


def run_proofread_check(text, task_type):
    """校审检查"""
    results = []
    for rule in PROOFREAD_RULES:
        passed = rule["check"](text)
        results.append({
            "rule_id": rule["id"],
            "rule_name": rule["name"],
            "status": "pass" if passed else (("warn" if rule["id"] in ["P02", "P03", "P04"] else "fail")),
            "description": rule["desc"],
        })
    return results


def check_task(project, task_id):
    """检查单个任务的产出"""
    task_dir = os.path.join(NFS_ROOT, "projects", project, "tasks")
    task = _read_json(os.path.join(task_dir, f"{task_id}.json"))
    if not task:
        print(f"❌ 任务 {task_id} 不存在")
        return None

    if task["status"] != "done":
        print(f"⏳ 任务 {task_id} 尚未完成（状态: {task['status']}），跳过检查")
        return None

    check_id = f"{task_id}-check"
    ttype = task.get("type", "")

    print(f"🔍 检查任务: {task_id} ({task.get('name', '')})")
    print(f"   类型: {ttype}")

    # 读取产出
    output_files = task.get("output_files", [])
    all_text = ""
    file_checks = {}

    for fpath in output_files:
        content = read_artifact(project, fpath)
        if content:
            all_text += f"\n\n=== {fpath} ===\n\n" + content
            file_checks[fpath] = {"found": True, "size": len(content)}
            print(f"   📄 读取产出: {fpath} ({len(content)} 字符)")
        else:
            file_checks[fpath] = {"found": False, "size": 0}
            print(f"   ⚠️ 文件未找到: {fpath}")

    # 如果产出的token估算很大，标记需校审人员关注
    est_tokens = task.get("estimated_tokens", 0)

    # 内容检查
    content_results = run_content_check(all_text, ttype)
    content_passed = all(r["status"] == "pass" for r in content_results)

    # 校审检查
    proofread_results = run_proofread_check(all_text, ttype)
    proofread_passed = all(r["status"] == "pass" for r in proofread_results)

    # 综合判定
    overall = "passed"
    issues = []

    if not content_passed:
        fails = [r for r in content_results if r["status"] == "fail"]
        issues.extend([f"内容检查: {f['rule_name']}" for f in fails])

    if not proofread_passed:
        fails = [r for r in proofread_results if r["status"] == "fail"]
        issues.extend([f"校审: {f['rule_name']}" for f in fails])

    if issues:
        overall = "failed"

    # 构建检查报告
    report = {
        "check_id": check_id,
        "task_id": task_id,
        "task_name": task.get("name"),
        "phase": task.get("phase"),
        "vm": task.get("vm"),
        "status": overall,
        "overall_verdict": overall,
        "estimated_tokens": est_tokens,
        "content_check": {
            "status": "passed" if content_passed else "failed",
            "items": content_results,
        },
        "proofread_check": {
            "status": "passed" if proofread_passed else "failed",
            "items": proofread_results,
        },
        "checklist": content_results + proofread_results,
        "issues": issues,
        "file_checks": file_checks,
        "intervention": None,
        "final_decision": "approved" if overall == "passed" else "needs_review",
        "checked_at": datetime.now().isoformat(),
    }

    if overall == "passed":
        print(f"\n✅ {check_id}: 全部通过")
        print(f"   内容: ✅ {len([r for r in content_results if r['status']=='pass'])}/{len(content_results)}")
        print(f"   校审: ✅ {len([r for r in proofread_results if r['status']=='pass'])}/{len(proofread_results)}")
    else:
        print(f"\n⚠️ {check_id}: 发现问题")
        for issue in issues:
            print(f"   ❌ {issue}")

    # 保存检查报告到项目级
    check_dir = os.path.join(NFS_ROOT, "projects", project, "check")
    _write_json(os.path.join(check_dir, f"{check_id}.json"), report)

    # 保存到检查智能体
    agent_check_dir = os.path.join(NFS_ROOT, "agents", "checker", "reports")
    _write_json(os.path.join(agent_check_dir, f"{check_id}.json"), report)

    # 更新检查智能体状态
    _write_json(os.path.join(NFS_ROOT, "agents", "checker", "state.json"), {
        "status": "idle" if overall == "passed" else "review_needed",
        "last_check_id": check_id,
        "last_verdict": overall,
        "last_checked_at": report["checked_at"],
        "pending_review": issues if issues else [],
    })

    return report


def check_all_phase(project, phase):
    """检查某阶段所有已完成任务"""
    tasks_dir = os.path.join(NFS_ROOT, "projects", project, "tasks")
    if not os.path.isdir(tasks_dir):
        print(f"❌ 无任务目录")
        return []

    results = []
    for fname in sorted(os.listdir(tasks_dir)):
        if fname.endswith(".json"):
            t = _read_json(os.path.join(tasks_dir, fname))
            if t and t.get("phase") == phase and t["status"] == "done":
                # 还检查过
                check_path = os.path.join(NFS_ROOT, "projects", project, "check", f"{t['task_id']}-check.json")
                if not os.path.exists(check_path):
                    r = check_task(project, t["task_id"])
                    if r: results.append(r)

    if not results:
        print(f"📋 {phase}: 无待检查的任务")

    return results


def show_report(project, check_id):
    """查看检查报告"""
    check_path = os.path.join(NFS_ROOT, "projects", project, "check", f"{check_id}.json")
    r = _read_json(check_path)
    if not r:
        # 也查一下全局的
        check_path = os.path.join(NFS_ROOT, "agents", "checker", "reports", f"{check_id}.json")
        r = _read_json(check_path)

    if not r:
        print(f"❌ 报告 {check_id} 不存在")
        return

    print(f"📋 检查报告: {r['check_id']}")
    print(f"   任务: {r.get('task_name', '?')} ({r['task_id']})")
    print(f"   判定: {'✅' if r['overall_verdict'] == 'passed' else '⚠️'} {r['overall_verdict']}")
    print(f"   检查时间: {r['checked_at']}")
    print()
    print(f"   ── 内容检查 ──")
    for item in r.get("content_check", {}).get("items", []):
        icon = "✅" if item["status"] == "pass" else "❌"
        print(f"   {icon} {item['rule_name']}: {item['status']}")
    print()
    print(f"   ── 校审检查 ──")
    for item in r.get("proofread_check", {}).get("items", []):
        icon = "✅" if item["status"] == "pass" else ("⚠️" if item["status"] == "warn" else "❌")
        print(f"   {icon} {item['rule_name']}: {item['status']}")
    if r.get("issues"):
        print(f"\n   问题列表:")
        for issue in r["issues"]:
            print(f"     ❌ {issue}")


def override_check(project, check_id, decision="approved", comment=""):
    """人工干预：覆盖检查结果"""
    check_path = os.path.join(NFS_ROOT, "projects", project, "check", f"{check_id}.json")
    r = _read_json(check_path)
    if not r:
        print(f"❌ 报告 {check_id} 不存在")
        return

    r["intervention"] = {
        "action": "override",
        "override_result": decision,
        "comment": comment or "人工确认通过",
        "issued_by": "human",
        "issued_at": datetime.now().isoformat(),
    }
    r["final_decision"] = decision

    _write_json(check_path, r)

    # 保存干预记录
    intervention = {
        "type": "check_override",
        "target": check_id,
        "action": "override",
        "override_result": decision,
        "comment": comment,
        "issued_by": "human",
        "issued_at": datetime.now().isoformat(),
    }
    _write_json(os.path.join(NFS_ROOT, "projects", project, "interventions", f"{check_id}-override.json"), intervention)

    print(f"✅ 人工干预已记录: {check_id} → {decision}")
    if comment:
        print(f"   备注: {comment}")


def main():
    if len(sys.argv) < 3:
        print("用法:")
        print("  python3 checker.py check <project> <task_id>")
        print("  python3 checker.py check-all <project> <phase>")
        print("  python3 checker.py report <project> <check_id>")
        print("  python3 checker.py override <project> <check_id> [decision] [comment]")
        sys.exit(1)

    cmd = sys.argv[1]
    project = sys.argv[2]

    if cmd == "check":
        if len(sys.argv) < 4:
            print("用法: python3 checker.py check <project> <task_id>")
            sys.exit(1)
        check_task(project, sys.argv[3])
    elif cmd == "check-all":
        if len(sys.argv) < 4:
            print("用法: python3 checker.py check-all <project> <phase>")
            sys.exit(1)
        check_all_phase(project, sys.argv[3])
    elif cmd == "report":
        if len(sys.argv) < 4:
            print("用法: python3 checker.py report <project> <check_id>")
            sys.exit(1)
        show_report(project, sys.argv[3])
    elif cmd == "override":
        if len(sys.argv) < 4:
            print("用法: python3 checker.py override <project> <check_id> [decision] [comment]")
            sys.exit(1)
        check_id = sys.argv[3]
        decision = sys.argv[4] if len(sys.argv) > 4 else "approved"
        comment = sys.argv[5] if len(sys.argv) > 5 else ""
        override_check(project, check_id, decision, comment)
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
