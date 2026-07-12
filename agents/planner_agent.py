#!/usr/bin/env python3
"""项目规划智能体 - 评估token、定粒度、选VM、出规划方案"""
import json, os, sys
from datetime import datetime

NFS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nfs-data")

# 加载token基线
def load_baselines():
    p = os.path.join(NFS, "knowledge/baselines/token-baselines.json")
    with open(p) as f:
        return json.load(f)

def load_project_status(project):
    p = os.path.join(NFS, f"projects/{project}/status.json")
    with open(p) as f:
        return json.load(f)

def load_vm_states():
    vms = {}
    for vm in ["vm1", "vm2", "vm3"]:
        p = os.path.join(NFS, f"agents/workers/{vm}/state.json")
        with open(p) as f:
            vms[vm] = json.load(f)
    return vms

def estimate_task(task_type, baselines):
    bl = baselines.get("baselines", {}).get(task_type, {"total": 16000})
    return bl["total"]

def plan_phase(project, phase, context):
    """核心规划逻辑：评估token → 定粒度 → 选VM → 输出规划方案"""
    baselines = load_baselines()
    status = load_project_status(project)
    vms = load_vm_states()

    # 1. 评估输入大小
    input_estimate = context.get("input_size", 50000)
    output_estimate = context.get("output_size", 30000)
    total_estimate = input_estimate + output_estimate

    # 2. 可用token预算
    vm_free = {vm: info.get("total_tokens_used", 0) for vm, info in vms.items()}
    available = {vm: 1048576 - used for vm, used in vm_free.items()}
    safety_margin = 0.3

    # 3. 粒度决策
    usable = max(available.values()) * (1 - safety_margin)
    if total_estimate <= usable:
        level = "stage"
        verdict = "level_ok"
    elif total_estimate <= usable * 0.5:
        level = "task"
        verdict = "need_decompose"
    else:
        level = "subtask"
        verdict = "decomposed"

    plan = {
        "plan_id": f"PLAN-{phase.upper()}-{project}",
        "project": project,
        "phase": phase,
        "level": level,
        "created_at": datetime.now().isoformat(),
        "token_budget": {
            "total_available": 1048576 * 3,
            "per_vm": 1048576,
            "safety_margin": safety_margin,
            "usable_per_vm": int(1048576 * (1 - safety_margin))
        },
        "assessment": {
            "input_size_estimate": input_estimate,
            "output_size_estimate": output_estimate,
            "total_estimate": total_estimate,
            "verdict": verdict
        },
        "items": context.get("tasks", []),
        "reasoning": (
            f"输入估算{input_estimate/1000:.0f}K + 输出估算{output_estimate/1000:.0f}K = "
            f"总需求{total_estimate/1000:.0f}K, 可用{int(usable/1000):.0f}K/VM. "
            f"结论: {verdict}. 采用{level}级粒度."
        )
    }
    return plan

def save_plan(project, plan):
    dir = os.path.join(NFS, f"projects/{project}/plans")
    path = os.path.join(dir, f"{plan['plan_id']}.json")
    with open(path, "w") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    # 同时写入 current.json
    with open(os.path.join(dir, "current.json"), "w") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    return path

if __name__ == "__main__":
    # CLI模式: python3 planner_agent.py <project> <phase> '<json_context>'
    if len(sys.argv) >= 3:
        project = sys.argv[1]
        phase = sys.argv[2]
        context = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        plan = plan_phase(project, phase, context)
        path = save_plan(project, plan)
        print(json.dumps({"status": "ok", "plan_path": path, "plan": plan}, ensure_ascii=False))
    else:
        print("Usage: planner_agent.py <project> <phase> [context_json]", file=sys.stderr)
