#!/usr/bin/env python3
"""编排智能体 - 读规划方案 → 按计划派发 → 收结果"""
import json, os, sys, time
from datetime import datetime

NFS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nfs-data")

def load_plan(project):
    p = os.path.join(NFS, f"projects/{project}/plans/current.json")
    with open(p) as f:
        return json.load(f)

def load_vm_states():
    vms = {}
    for vm in ["vm1", "vm2", "vm3"]:
        p = os.path.join(NFS, f"agents/workers/{vm}/state.json")
        with open(p) as f:
            vms[vm] = json.load(f)
    return vms

def update_vm_state(vm, data):
    p = os.path.join(NFS, f"agents/workers/{vm}/state.json")
    with open(p, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def update_status(project, phase, task_id, status):
    p = os.path.join(NFS, f"projects/{project}/status.json")
    with open(p) as f:
        st = json.load(f)
    if phase in st.get("phases", {}):
        st["phases"][phase]["status"] = status
    st["updated_at"] = datetime.now().isoformat()
    with open(p, "w") as f:
        json.dump(st, f, indent=2, ensure_ascii=False)

def dispatch(project):
    """读取规划方案，找出所有可派发的pending任务，分配给空闲VM"""
    plan = load_plan(project)
    vms = load_vm_states()
    dispatched = []

    for item in plan.get("items", []):
        task_id = item["task_id"]
        task_path = os.path.join(NFS, f"projects/{project}/tasks/{task_id}.json")
        if not os.path.exists(task_path):
            continue
        with open(task_path) as f:
            task = json.load(f)
        if task["status"] != "pending":
            continue

        # 检查依赖是否全部完成
        deps = task.get("depends_on", [])
        deps_ok = True
        for dep_id in deps:
            dep_path = os.path.join(NFS, f"projects/{project}/tasks/{dep_id}.json")
            if os.path.exists(dep_path):
                with open(dep_path) as f:
                    dep = json.load(f)
                if dep["status"] != "completed":
                    deps_ok = False
                    break
        if not deps_ok:
            continue

        # 找空闲VM
        assignee = item.get("assignee", "vm1")
        vm_state = vms.get(assignee, {})
        if vm_state.get("status") == "idle":
            # 派发
            task["status"] = "running"
            task["started_at"] = datetime.now().isoformat()
            with open(task_path, "w") as f:
                json.dump(task, f, indent=2, ensure_ascii=False)

            vm_state["status"] = "busy"
            vm_state["current_task"] = task_id
            update_vm_state(assignee, vm_state)

            dispatched.append({"task_id": task_id, "assignee": assignee, "vm": assignee})

    return dispatched

def collect_results(project):
    """检查所有running状态的任务是否已完成，收集结果"""
    plan = load_plan(project)
    vms = load_vm_states()
    collected = []

    for item in plan.get("items", []):
        task_id = item["task_id"]
        task_path = os.path.join(NFS, f"projects/{project}/tasks/{task_id}.json")
        if not os.path.exists(task_path):
            continue
        with open(task_path) as f:
            task = json.load(f)
        if task["status"] != "running":
            continue

        # 检查worker是否已完成
        assignee = item.get("assignee", "vm1")
        vm_state = vms.get(assignee, {})
        if vm_state.get("status") == "idle" or vm_state.get("current_task") != task_id:
            # Worker已释放，任务应已完成，重新检查状态文件
            with open(task_path) as f:
                task = json.load(f)
            if task["status"] == "completed":
                collected.append({"task_id": task_id, "status": "completed"})
                continue

        # 检查是否有结果文件
        for output in task.get("output_refs", []):
            out_path = os.path.join(NFS, output["path"])
            if os.path.exists(out_path) and output["path"].endswith(".json"):
                with open(out_path) as f:
                    result = json.load(f)
                if isinstance(result, dict) and result.get("status") == "completed":
                    task["status"] = "completed"
                    task["completed_at"] = datetime.now().isoformat()
                    with open(task_path, "w") as f:
                        json.dump(task, f, indent=2, ensure_ascii=False)

                    vm_state["status"] = "idle"
                    vm_state["current_task"] = None
                    update_vm_state(assignee, vm_state)
                    collected.append({"task_id": task_id, "status": "completed"})
                    break

    return collected

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "tick"
    project = sys.argv[2] if len(sys.argv) > 2 else "demo-project"

    if action == "dispatch":
        result = dispatch(project)
        print(json.dumps({"action": "dispatch", "dispatched": result}, ensure_ascii=False))
    elif action == "collect":
        result = collect_results(project)
        print(json.dumps({"action": "collect", "collected": result}, ensure_ascii=False))
    elif action == "tick":
        # 一个完整编排周期
        dispatched = dispatch(project)
        collected = collect_results(project)
        print(json.dumps({
            "action": "tick",
            "project": project,
            "dispatched": dispatched,
            "collected": collected
        }, ensure_ascii=False))
