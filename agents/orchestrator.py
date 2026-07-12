#!/usr/bin/env python3
"""
售前智能体 · 编排智能体 (Orchestrator Agent)
职责：读规划方案 → 按计划派发任务 → 监控进度 → 收结果 → 推进阶段
用法：
  python3 orchestrator.py dispatch <project>                  # 派发当前阶段所有就绪任务
  python3 orchestrator.py status <project>                    # 查看编排状态
  python3 orchestrator.py advance <project>                   # 推进到下一阶段
"""
import json, os, sys, glob
from datetime import datetime

NFS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "nfs-data")

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

def _update_status(project, updates):
    spath = os.path.join(NFS_ROOT, "projects", project, "status.json")
    st = _read_json(spath) or {}
    st.update(updates)
    st["updated_at"] = datetime.now().isoformat()
    _write_json(spath, st)


def dispatch_tasks(project):
    """派发当前阶段所有依赖就绪的任务"""
    status = _read_json(os.path.join(NFS_ROOT, "projects", project, "status.json"))
    if not status:
        print(f"❌ 项目 {project} 不存在")
        return

    phase = status.get("current_phase")
    if not phase:
        print(f"❌ 项目 {project} 未设定当前阶段")
        return

    # 读规划方案
    plan = _read_json(os.path.join(NFS_ROOT, "projects", project, "plans", "current.json"))
    if not plan:
        print(f"❌ 当前无规划方案，请先运行 planner.py plan {project} {phase}")
        return

    tasks_dir = os.path.join(NFS_ROOT, "projects", project, "tasks")
    existing = {}
    if os.path.isdir(tasks_dir):
        for fname in os.listdir(tasks_dir):
            if fname.endswith(".json"):
                t = _read_json(os.path.join(tasks_dir, fname))
                if t: existing[t["task_id"]] = t

    # 检查各子节点的依赖是否就绪
    dispatched = []
    skipped = []
    blocked = []

    for t_def in plan.get("task_breakdown", []):
        tid = t_def["task_id"]
        deps = t_def.get("dependencies", [])

        # 已存在且非pending, 跳过
        if tid in existing and existing[tid]["status"] != "pending":
            dispatched.append(tid)
            continue

        # 检查依赖
        deps_ready = True
        for dep_id in deps:
            if dep_id not in existing:
                deps_ready = False
                break
            if existing[dep_id]["status"] != "done":
                deps_ready = False
                break

        if not deps_ready:
            blocked.append(tid)
            continue

        # 构造任务JSON
        task = {
            "task_id": tid,
            "name": t_def["name"],
            "type": t_def["type"],
            "phase": phase,
            "vm": t_def.get("vm", "vm1"),
            "status": "pending",
            "dependencies": deps,
            "input_files": t_def.get("input_files", []),
            "output_files": [],
            "estimated_tokens": t_def.get("estimated_tokens", 0),
            "token_budget": {
                "max_input": int(64000 * 0.55),
                "max_output": int(64000 * 0.35),
                "estimated": t_def.get("estimated_tokens", 0),
            },
            "self_check_required": True if "check" not in tid else False,
            "check_task_id": f"{tid}-check",
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "result_summary": None,
        }
        _write_json(os.path.join(tasks_dir, f"{tid}.json"), task)
        dispatched.append(tid)
        print(f"  ✅ 已创建任务: {tid} ({t_def['name']}) → {task['vm']}")

    # 更新编排状态
    orch_state = {
        "project": project,
        "current_phase": phase,
        "status": "running",
        "dispatched_count": len(dispatched),
        "blocked_count": len(blocked),
        "completed_tasks": [],
        "failed_tasks": [],
        "last_dispatch": datetime.now().isoformat(),
    }

    _write_json(os.path.join(NFS_ROOT, "agents", "orchestrator", "state.json"), orch_state)

    print(f"\n📊 派发汇总")
    print(f"   已派发: {len(dispatched)} 个")
    print(f"   阻塞(依赖未就绪): {len(blocked)} 个")
    if blocked:
        print(f"   阻塞列表: {', '.join(blocked)}")

    return dispatched


def show_status(project):
    """查看编排状态"""
    status = _read_json(os.path.join(NFS_ROOT, "projects", project, "status.json"))
    orch = _read_json(os.path.join(NFS_ROOT, "agents", "orchestrator", "state.json"))

    if not status:
        print(f"❌ 项目 {project} 不存在")
        return

    phase = status.get("current_phase", "—")
    print(f"🔀 编排状态 · {project}")
    print(f"   当前阶段: {phase}")
    print(f"   项目状态: {status.get('status', '?')}")
    print(f"   阶段进度: ")

    for pname, info in status.get("phase_progress", {}).items():
        done = info["tasks_completed"]
        total = info["tasks_total"]
        pushed = "📤" if info.get("pushed") else "🕐"
        print(f"     {pname}: {done}/{total} 完成 {pushed}")

    if orch:
        print(f"\n   编排器状态: {orch.get('status', '?')}")
        print(f"   已派发: {orch.get('dispatched_count', 0)}")
        print(f"   已完成: {len(orch.get('completed_tasks', []))}")
        print(f"   失败: {len(orch.get('failed_tasks', []))}")


def advance_phase(project):
    """推进到下一阶段"""
    seq = ["research", "framework", "design", "ppt"]
    status = _read_json(os.path.join(NFS_ROOT, "projects", project, "status.json"))
    if not status:
        print(f"❌ 项目 {project} 不存在")
        return

    current = status.get("current_phase")
    if current and current in seq:
        idx = seq.index(current)
        if idx + 1 >= len(seq):
            print(f"✅ 所有阶段已完成! 准备最终推送")
            _update_status(project, {"status": "completed", "current_phase": None})
            return
        next_phase = seq[idx + 1]
    else:
        next_phase = seq[0]

    _update_status(project, {
        "current_phase": next_phase,
        "status": "running"
    })

    # 重置编排状态
    _write_json(os.path.join(NFS_ROOT, "agents", "orchestrator", "state.json"), {
        "project": project,
        "current_phase": next_phase,
        "status": "ready",
        "dispatched_count": 0,
        "completed_tasks": [],
        "failed_tasks": [],
    })

    print(f"➡️ 推进到下一阶段: {next_phase}")
    print(f"  请执行: python3 planner.py plan {project} {next_phase}")
    print(f"  然后: python3 orchestrator.py dispatch {project}")


def main():
    if len(sys.argv) < 3:
        print("用法:")
        print("  python3 orchestrator.py dispatch <project>   # 派发当前阶段就绪任务")
        print("  python3 orchestrator.py status <project>     # 查看编排状态")
        print("  python3 orchestrator.py advance <project>    # 推进到下一阶段")
        sys.exit(1)

    cmd = sys.argv[1]
    project = sys.argv[2]

    if cmd == "dispatch":
        dispatch_tasks(project)
    elif cmd == "status":
        show_status(project)
    elif cmd == "advance":
        advance_phase(project)
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
