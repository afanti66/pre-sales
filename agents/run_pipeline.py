#!/usr/bin/env python3
"""全线启动脚本 - 模拟 pipeline 全自动流程"""
import json, os, sys, subprocess
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(__file__))
AGENTS = os.path.join(BASE, "agents")
NFS = os.path.join(BASE, "nfs-data")

def run_agent(script, *args):
    cmd = [sys.executable, os.path.join(AGENTS, script)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERROR] {script}: {result.stderr[:500]}")
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"[WARN] 无法解析输出: {result.stdout[:200]}")
        return result.stdout

def print_separator(title):
    w = 60
    print(f"\n{'='*w}")
    print(f"  {title}")
    print(f"{'='*w}")

def load_task_assignee(task_id, project):
    """从task JSON文件读取assignee"""
    p = os.path.join(NFS, f"projects/{project}/tasks/{task_id}.json")
    if os.path.exists(p):
        with open(p) as f:
            task = json.load(f)
        return task.get("assignee", "vm1")
    return "vm1"

def run_worker(task_id, project):
    """自动读取task的assignee后执行worker_agent"""
    vm = load_task_assignee(task_id, project)
    return run_agent("worker_agent.py", vm, task_id, project)

def tick_orchestrator(project):
    """编排代理执行一次tick"""
    result = run_agent("orchestrator_agent.py", "tick", project)
    if isinstance(result, dict):
        d = result.get("dispatched", [])
        c = result.get("collected", [])
        if d:
            for item in d:
                print(f"  → 派发: {item['task_id']} → {item['vm']}")
        if c:
            for item in c:
                print(f"  ✓ 回收: {item['task_id']} ({item.get('status','?')})")
    return result

def main():
    import time
    project = sys.argv[1] if len(sys.argv) > 1 else "demo-project"

    print_separator("🚀 售前智能体管线启动")
    print(f"项目: {project}")
    print(f"时间: {datetime.now().isoformat()}")
    print(f"模型: DeepSeek v4 Flash (1M上下文)")
    print(f"VM集群: 3台 (vm1/vm2/vm3)")

    # === Phase 1: 调研阶段 ===
    print_separator("📋 Phase 1: 调研阶段 (Research)")
    print("规划智能体 → 评估token、定粒度、出方案")
    plan_research = {
        "input_size": 12000,
        "output_size": 18000,
        "tasks": [
            {"task_id": "research-001-outline", "level": "task", "assignee": "vm1", "estimated_tokens": 12000, "depends_on": [], "description": "方案大纲"},
            {"task_id": "research-002-literature", "level": "task", "assignee": "vm2", "estimated_tokens": 16000, "depends_on": [], "description": "文献知识"},
            {"task_id": "research-003-solution", "level": "task", "assignee": "vm3", "estimated_tokens": 20000, "depends_on": [], "description": "方案知识"},
            {"task_id": "check-research", "level": "task", "assignee": "vm1", "estimated_tokens": 12000, "depends_on": ["research-001-outline", "research-002-literature", "research-003-solution"], "description": "检查+校审"}
        ]
    }
    run_agent("planner_agent.py", project, "research", json.dumps(plan_research))

    print("编排代理 → 派发调研子任务到3台VM并行执行")
    tick_orchestrator(project)

    print("\nWorker执行调研任务...")
    for task_id in ["research-001-outline", "research-002-literature", "research-003-solution"]:
        run_worker(task_id, project)

    tick_orchestrator(project)
    # 跑检查任务Worker
    run_worker("check-research", project)
    tick_orchestrator(project)
    print("检查+校审 → 调研阶段")
    check_result = run_agent("checker_agent.py", "check", project, "research")
    if check_result:
        print(f"  检查状态: {check_result.get('status')}")
        print(f"  校审问题: {len(check_result.get('proofreading', {}).get('issues', []))}项")
        run_agent("checker_agent.py", "push", project, "research")

    # === Phase 2: 框架阶段 ===
    print_separator("📋 Phase 2: 框架阶段 (Framework)")
    plan_framework = {
        "input_size": 30000,
        "output_size": 20000,
        "tasks": [
            {"task_id": "framework-001-matrix", "level": "task", "assignee": "vm1", "estimated_tokens": 15000, "depends_on": ["research-001-outline", "research-003-solution"], "description": "需求矩阵"},
            {"task_id": "framework-002-business", "level": "task", "assignee": "vm2", "estimated_tokens": 14000, "depends_on": ["research-002-literature"], "description": "业务框架"},
            {"task_id": "framework-003-system", "level": "task", "assignee": "vm3", "estimated_tokens": 20000, "depends_on": ["research-001-outline", "research-003-solution"], "description": "系统框架"},
            {"task_id": "check-framework", "level": "task", "assignee": "vm2", "estimated_tokens": 18000, "depends_on": ["framework-001-matrix", "framework-002-business", "framework-003-system"], "description": "检查+校审"}
        ]
    }
    run_agent("planner_agent.py", project, "framework", json.dumps(plan_framework))
    tick_orchestrator(project)
    for task_id in ["framework-001-matrix", "framework-002-business", "framework-003-system"]:
        run_worker(task_id, project)
    tick_orchestrator(project)
    run_worker("check-framework", project)
    tick_orchestrator(project)
    run_agent("checker_agent.py", "check", project, "framework")
    run_agent("checker_agent.py", "push", project, "framework")

    # === Phase 3: 设计阶段 ===
    print_separator("📋 Phase 3: 设计阶段 (Design - 7子节点)")
    plan_design = {
        "input_size": 50000,
        "output_size": 60000,
        "tasks": [
            {"task_id": "design-001-requirement", "level": "stage", "assignee": "vm1", "estimated_tokens": 16000, "depends_on": ["framework-001-matrix", "framework-002-business"], "description": "需求分析"},
            {"task_id": "design-002-overall", "level": "stage", "assignee": "vm2", "estimated_tokens": 20000, "depends_on": ["framework-003-system"], "description": "总体方案"},
            {"task_id": "design-003-subproject", "level": "stage", "assignee": "vm3", "estimated_tokens": 25000, "depends_on": ["framework-003-system"], "description": "分项方案"},
            {"task_id": "design-004-common", "level": "stage", "assignee": "vm1", "estimated_tokens": 13000, "depends_on": ["framework-003-system"], "description": "公共部分"}
        ]
    }
    run_agent("planner_agent.py", project, "design", json.dumps(plan_design))
    tick_orchestrator(project)

    for task_id in ["design-001-requirement", "design-002-overall", "design-003-subproject", "design-004-common"]:
        run_worker(task_id, project)
    tick_orchestrator(project)

    for task_id in ["design-005-prototype", "design-006-budget"]:
        run_worker(task_id, project)
    tick_orchestrator(project)

    run_worker("design-007-diagrams", project)
    tick_orchestrator(project)

    run_worker("check-design", project)
    tick_orchestrator(project)
    run_agent("checker_agent.py", "check", project, "design")
    run_agent("checker_agent.py", "push", project, "design")

    # === Phase 4: PPT ===
    print_separator("📋 Phase 4: PPT阶段")
    plan_ppt = {
        "input_size": 50000,
        "output_size": 10000,
        "tasks": [
            {"task_id": "ppt-001", "level": "task", "assignee": "vm3", "estimated_tokens": 35000, "depends_on": ["design-007-diagrams"], "description": "PPT制作"},
            {"task_id": "check-ppt", "level": "task", "assignee": "vm2", "estimated_tokens": 18000, "depends_on": ["ppt-001"], "description": "PPT检查+校审"}
        ]
    }
    run_agent("planner_agent.py", project, "ppt", json.dumps(plan_ppt))
    tick_orchestrator(project)
    run_worker("ppt-001", project)
    tick_orchestrator(project)
    run_worker("check-ppt", project)
    tick_orchestrator(project)
    run_agent("checker_agent.py", "check", project, "ppt")
    run_agent("checker_agent.py", "push", project, "ppt")

    # === 完成 ===
    print_separator("✅ 全管线执行完毕")
    print("各阶段产出已检查+校审，推送至后台文档服务")
    print(f"查看看板: http://192.168.2.9:8080")

if __name__ == "__main__":
    main()
