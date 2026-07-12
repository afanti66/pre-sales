#!/usr/bin/env python3
"""
售前智能体 · 规划智能体 (Planner Agent)
职责：评估token预算 → 定粒度(阶段/子阶段/任务/子任务) → 选VM → 出规划方案
用法：
  python3 planner.py plan <project> <phase>        # 生成规划方案
  python3 planner.py baseline <project>             # 更新token基线
  python3 planner.py status                         # 查看规划状态
"""
import json, os, sys, glob
from datetime import datetime

NFS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "nfs-data")
SAFE_MARGIN = 0.30              # 安全边际30%
VM_CAPACITY = 64000             # 单VM 64K
MAX_INPUT_RATIO = 0.55          # 输入占用不超过55%

# Token基线数据库 (按任务类型)
TOKEN_BASELINE = {
    "research-outline":   {"input_avg": 8000,  "output_avg": 6000,  "desc": "方案大纲起草"},
    "research-literature":{"input_avg": 10000, "output_avg": 8000,  "desc": "文献知识整理"},
    "research-solution":  {"input_avg": 12000, "output_avg": 8000,  "desc": "方案知识整理"},
    "framework-matrix":   {"input_avg": 10000, "output_avg": 6000,  "desc": "需求矩阵"},
    "framework-business": {"input_avg": 8000,  "output_avg": 8000,  "desc": "业务框架"},
    "framework-system":   {"input_avg": 10000, "output_avg": 10000, "desc": "系统框架"},
    "design-requirement": {"input_avg": 8000,  "output_avg": 6000,  "desc": "需求分析章节"},
    "design-overall":     {"input_avg": 6000,  "output_avg": 8000,  "desc": "总体方案章节"},
    "design-module":      {"input_avg": 6000,  "output_avg": 10000, "desc": "分项方案章节"},
    "design-common":      {"input_avg": 4000,  "output_avg": 4000,  "desc": "公共部分章节"},
    "design-prototype":   {"input_avg": 6000,  "output_avg": 8000,  "desc": "原型设计章节"},
    "design-budget":      {"input_avg": 8000,  "output_avg": 6000,  "desc": "预算方案章节"},
    "design-diagram":     {"input_avg": 15000, "output_avg": 12000, "desc": "图例汇总(转drawio+PNG)"},
    "design-check":       {"input_avg": 25000, "output_avg": 4000,  "desc": "设计阶段检查+校审"},
    "ppt":                {"input_avg": 20000, "output_avg": 8000,  "desc": "PPT生成"},
    "ppt-check":          {"input_avg": 15000, "output_avg": 3000,  "desc": "PPT检查+校审"},
}

# ===== 辅助函数 =====

def _read_json(path):
    if not os.path.exists(path): return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return None

def _write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _read_input_files(proj, file_list):
    """读取输入文件，统计token量"""
    total = 0
    files = []
    for fname in (file_list or []):
        fpath = os.path.join(NFS_ROOT, "projects", proj, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            tok = len(content)  # 粗略估算：中文字符≈2token
            total += tok
            files.append(fname)
    return total, files

def _estimate_task(task_type, input_adj=1.0):
    """根据基线+调整因子估算token"""
    base = TOKEN_BASELINE.get(task_type)
    if not base:
        return {"input": 8000, "output": 4000, "total": 12000}
    inp = int(base["input_avg"] * input_adj)
    out = int(base["output_avg"])
    return {"input": inp, "output": out, "total": inp + out}

def _safe_threshold():
    return int(VM_CAPACITY * (1 - SAFE_MARGIN))

def _decide_granularity(task_estimates, threshold):
    """根据token总量决定粒度"""
    total_est = sum(t["estimated_tokens"] for t in task_estimates)

    if total_est <= threshold:
        return "phase", "一阶段单对话完成, token充足"
    elif total_est <= threshold * 2:
        return "sub-stage", "超出单阶段安全线, 拆为子阶段并行"
    elif total_est <= threshold * 3:
        return "task", "需拆为多个任务并行+串行"
    else:
        return "sub-task", "超大规模, 需精细拆分为子任务级"

# ===== 规划引擎 =====

def generate_plan(project, phase, override_granularity=None):
    """生成规划方案"""
    status = _read_json(os.path.join(NFS_ROOT, "projects", project, "status.json"))
    if not status:
        print(f"❌ 项目 {project} 状态文件不存在")
        return None

    # 获取当前阶段的任务定义
    plan_id = f"PLAN-{phase.upper()}-{datetime.now().strftime('%H%M%S')}"
    threshold = _safe_threshold()

    # ===== 根据阶段定义任务 =====
    phase_tasks = []

    if phase == "research":
        phase_tasks = [
            {"task_id": f"{phase}-001-outline",    "name": "方案大纲起草",     "type": "research-outline",    "vm": "vm1", "deps": [],                         "input_files": ["input/requirements.md", "input/references.md"]},
            {"task_id": f"{phase}-002-literature", "name": "文献知识整理",     "type": "research-literature","vm": "vm2", "deps": [],                         "input_files": ["input/references.md"]},
            {"task_id": f"{phase}-003-solution",   "name": "方案知识整理",     "type": "research-solution",  "vm": "vm3", "deps": [f"{phase}-001-outline"],  "input_files": ["input/requirements.md"]},
        ]
    elif phase == "framework":
        phase_tasks = [
            {"task_id": f"{phase}-001-matrix",     "name": "需求矩阵",          "type": "framework-matrix",   "vm": "vm1", "deps": [],                         "input_files": ["artifacts/research/outline.md", "artifacts/research/literature.md"]},
            {"task_id": f"{phase}-002-business",   "name": "业务框架",          "type": "framework-business", "vm": "vm2", "deps": [],                         "input_files": ["artifacts/research/outline.md"]},
            {"task_id": f"{phase}-003-system",     "name": "系统框架",          "type": "framework-system",   "vm": "vm3", "deps": [f"{phase}-002-business"],  "input_files": ["artifacts/research/outline.md", "artifacts/research/solution.md"]},
        ]
    elif phase == "design":
        phase_tasks = [
            {"task_id": f"{phase}-001-requirement","name": "需求分析章节",      "type": "design-requirement", "vm": "vm1", "deps": [],                         "input_files": ["artifacts/framework/matrix.md", "input/requirements.md"]},
            {"task_id": f"{phase}-002-overall",    "name": "总体方案章节",      "type": "design-overall",     "vm": "vm2", "deps": [],                         "input_files": ["artifacts/framework/system.md"]},
            {"task_id": f"{phase}-003-module",     "name": "分项方案章节",      "type": "design-module",      "vm": "vm3", "deps": [],                         "input_files": ["artifacts/framework/system.md", "artifacts/framework/business.md"]},
            {"task_id": f"{phase}-004-common",     "name": "公共部分章节",      "type": "design-common",      "vm": "vm1", "deps": [],                         "input_files": ["artifacts/framework/background.md"]},
            # 串行触发
            {"task_id": f"{phase}-005-prototype",  "name": "原型设计章节",      "type": "design-prototype",   "vm": "vm2", "deps": [f"{phase}-001-requirement"], "input_files": ["artifacts/design/requirement.md"]},
            {"task_id": f"{phase}-006-budget",     "name": "预算方案章节",      "type": "design-budget",      "vm": "vm3", "deps": [f"{phase}-003-module"],     "input_files": ["artifacts/design/module.md"]},
            # 汇总(等所有子节点完成)
            {"task_id": f"{phase}-007-diagram",    "name": "图例汇总(标准版)",  "type": "design-diagram",     "vm": "vm1", "deps": [f"{phase}-001-requirement", f"{phase}-002-overall", f"{phase}-003-module", f"{phase}-004-common", f"{phase}-005-prototype"],  "input_files": None},  # 动态读取各子节点产出
        ]
    elif phase == "ppt":
        phase_tasks = [
            {"task_id": "ppt-001", "name": "PPT生成", "type": "ppt", "vm": "vm1", "deps": [], "input_files": ["artifacts/design/"]},
        ]
    else:
        print(f"❌ 未知阶段: {phase}")
        return None

    # ===== 估算每个任务的token =====
    task_estimates = []
    for t in phase_tasks:
        est = _estimate_task(t["type"])
        task_estimates.append({
            "task_id": t["task_id"],
            "name": t["name"],
            "type": t["type"],
            "estimated_tokens": est["total"],
            "input_estimate": est["input"],
            "output_estimate": est["output"],
            "vm": t["vm"],
            "dependencies": t["deps"],
        })

    total_estimated = sum(e["estimated_tokens"] for e in task_estimates)
    per_vm = {}
    for e in task_estimates:
        vm = e["vm"]
        if vm not in per_vm: per_vm[vm] = 0
        per_vm[vm] += e["estimated_tokens"]

    # ===== 决定粒度 =====
    if override_granularity:
        granularity = override_granularity
    else:
        granularity, reason = _decide_granularity(task_estimates, threshold)

    # ===== 并行/串行分组 =====
    parallel_count = len([t for t in phase_tasks if len(t["deps"]) == 0])
    sequential_groups = len(set(",".join(t["deps"]) for t in phase_tasks if t["deps"]))

    # ===== 构建规划方案 =====
    plan = {
        "plan_id": plan_id,
        "project": project,
        "phase": phase,
        "granularity": granularity,
        "token_assessment": {
            "total_estimate": total_estimated,
            "per_vm_estimate": per_vm,
            "vm_capacity": VM_CAPACITY,
            "safety_margin_pct": int(SAFE_MARGIN * 100),
            "safe_threshold": threshold,
            "is_safe": all(v <= threshold for v in per_vm.values()),
            "bottleneck": max(per_vm, key=per_vm.get) if per_vm else None,
            "bottleneck_load": max(per_vm.values()) if per_vm else 0,
        },
        "total_tasks": len(phase_tasks),
        "expected_parallel": parallel_count,
        "expected_sequential_groups": sequential_groups,
        "cluster_assignment": {},
        "task_breakdown": task_estimates,
        "planner_notes": f"基于{len(TOKEN_BASELINE)}类任务基线库估算",
        "created_at": datetime.now().isoformat(),
    }

    # ===== 集群分配 =====
    for vm_id in ["vm1", "vm2", "vm3"]:
        vm_tasks = [t for t in phase_tasks if t["vm"] == vm_id] if granularity == "task" else [t for t in phase_tasks if t["vm"] == vm_id]
        plan["cluster_assignment"][vm_id] = {
            "role": "worker",
            "task_ids": [t["task_id"] for t in vm_tasks] if granularity == "task" else [],
            "load": per_vm.get(vm_id, 0)
        }

    # 如果是阶段级，都放vm1
    if granularity == "phase":
        plan["cluster_assignment"]["vm1"]["task_ids"] = [t["task_id"] for t in phase_tasks]
        plan["cluster_assignment"]["vm1"]["role"] = "master"
        plan["cluster_assignment"]["vm2"]["task_ids"] = []
        plan["cluster_assignment"]["vm3"]["task_ids"] = []

    return plan


def save_plan(project, plan):
    """保存规划方案"""
    # 写入项目级
    plan_dir = os.path.join(NFS_ROOT, "projects", project, "plans")
    _write_json(os.path.join(plan_dir, f"{plan['plan_id']}.json"), plan)
    # 更新当前方案
    _write_json(os.path.join(plan_dir, "current.json"), plan)
    # 同步写入全局
    _write_json(os.path.join(NFS_ROOT, "plans", f"{plan['plan_id']}.json"), plan)
    print(f"✅ 规划方案已保存: {plan['plan_id']}")
    print(f"   阶段: {plan['phase']} | 粒度: {plan['granularity']} | 任务数: {plan['total_tasks']}")
    print(f"   Token估算: {plan['token_assessment']['total_estimate']}, 安全阈值: {plan['token_assessment']['safe_threshold']}")
    print(f"   安全: {'✅' if plan['token_assessment']['is_safe'] else '⚠️ 超出安全线, 需拆! '}")
    return plan


def show_status():
    """查看规划智能体状态"""
    state_path = os.path.join(NFS_ROOT, "agents", "planner", "state.json")
    state = _read_json(state_path) or {}

    plans_dir = os.path.join(NFS_ROOT, "plans")
    plans = sorted(glob.glob(os.path.join(plans_dir, "*.json"))) if os.path.isdir(plans_dir) else []

    print(f"🧠 规划智能体状态")
    print(f"   状态: {state.get('status', 'idle')}")
    print(f"   基线库: {len(TOKEN_BASELINE)} 类任务")
    print(f"   已生成方案: {len(plans)} 个")
    print(f"   安全阈值: {_safe_threshold()}/64K ({int(SAFE_MARGIN*100)}%安全边际)")
    print()
    for p in plans[-3:]:
        plan = _read_json(p)
        if plan:
            print(f"   📋 {plan['plan_id']}: {plan['project']}/{plan['phase']} | {plan['granularity']} | {plan['token_assessment']['total_estimate']}tok")

    total_used = state.get("token_used", {})
    if total_used:
        print(f"\n   Token累计消耗:")
        for tp, cnt in sorted(total_used.items()):
            print(f"     {tp}: {cnt}")


# ===== CLI入口 =====

def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 planner.py plan <project> <phase> [granularity]")
        print("  python3 planner.py baseline <project>")
        print("  python3 planner.py status")
        print()
        print("阶段: research | framework | design | ppt")
        print("粒度(可选): phase | sub-stage | task | sub-task")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "plan":
        if len(sys.argv) < 4:
            print("用法: python3 planner.py plan <project> <phase> [granularity]")
            sys.exit(1)
        project = sys.argv[2]
        phase = sys.argv[3]
        override = sys.argv[4] if len(sys.argv) > 4 else None

        plan = generate_plan(project, phase, override)
        if plan:
            save_plan(project, plan)

    elif cmd == "baseline":
        project = sys.argv[2] if len(sys.argv) > 2 else "default"
        # 从已完成任务的token消耗更新基线
        print(f"📊 更新 {project} 的token基线 (功能暂为存根)")
        pass

    elif cmd == "status":
        show_status()

    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
