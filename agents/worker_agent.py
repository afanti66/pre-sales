#!/usr/bin/env python3
"""Worker子代理 - 执行原子任务，用足自己的64K"""
import json, os, sys, subprocess
from datetime import datetime

NFS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nfs-data")

def load_task(task_id, project):
    p = os.path.join(NFS, f"projects/{project}/tasks/{task_id}.json")
    with open(p) as f:
        return json.load(f)

def update_task(task, project):
    p = os.path.join(NFS, f"projects/{project}/tasks/{task['task_id']}.json")
    with open(p, "w") as f:
        json.dump(task, f, indent=2, ensure_ascii=False)

def load_vm_state(vm):
    p = os.path.join(NFS, f"agents/workers/{vm}/state.json")
    with open(p) as f:
        return json.load(f)

def save_vm_state(vm, state):
    p = os.path.join(NFS, f"agents/workers/{vm}/state.json")
    with open(p, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def read_inputs(task):
    """读取任务的输入文件或目录，返回内容字典"""
    import glob
    contents = {}
    for ref in task.get("input_refs", []):
        p = os.path.join(NFS, ref["path"])
        if not os.path.exists(p):
            contents[ref["description"]] = f"[FILE NOT FOUND: {p}]"
            continue
        if os.path.isfile(p):
            with open(p) as f:
                contents[ref["description"]] = f.read()
        elif os.path.isdir(p):
            # 目录：读取目录下所有文件
            dir_contents = {}
            for fn in sorted(os.listdir(p)):
                fp = os.path.join(p, fn)
                if os.path.isfile(fp):
                    with open(fp) as f:
                        dir_contents[fn] = f.read()
            contents[ref["description"]] = json.dumps(dir_contents, indent=2, ensure_ascii=False)
    return contents

def execute(task, vm):
    """核心执行逻辑"""
    import sys as _sys
    def log(msg):
        print(msg, file=_sys.stderr)

    log(f"[{vm}] 执行任务: {task['task_id']} ({task.get('description', '')})")
    log(f"[{vm}]  输入依赖: {[r['description'] for r in task.get('input_refs', [])]}")

    inputs = read_inputs(task)
    total_input_size = sum(len(v) for v in inputs.values())
    log(f"[{vm}]  输入总大小: {total_input_size} chars (~{total_input_size//3} tokens)")

    # 模拟生成输出
    for ref in task.get("output_refs", []):
        out_path = os.path.join(NFS, ref["path"])
        # 如果路径以/结尾或是目录，追加一个默认文件名
        if out_path.endswith('/') or os.path.isdir(out_path):
            safe_name = ref["description"].replace(' ', '-').replace('/', '-')[:40] + ".md"
            out_path = os.path.join(out_path, safe_name)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        content = (
            f"# {ref['description']}\n\n"
            f"**任务**: {task['task_id']}\n"
            f"**执行VM**: {vm}\n"
            f"**时间**: {datetime.now().isoformat()}\n\n"
            f"## 内容摘要\n\n"
            f"基于输入:\n"
        )
        for desc, val in inputs.items():
            lines = val.strip().split('\n')
            preview = '\n'.join(lines[:3]) + ('\n...' if len(lines) > 3 else '')
            content += f"- {desc} ({len(lines)}行):\n  {preview[:200]}\n"
        content += f"\n---\n\n*该输出由Worker代理在VM {vm} 上生成*\n"

        with open(out_path, "w") as f:
            f.write(content)
        log(f"[{vm}]  已生成: {out_path}")

    # 更新task状态
    task["status"] = "completed"
    task["completed_at"] = datetime.now().isoformat()
    task["actual_tokens"] = total_input_size // 3 + 2000
    update_task(task, project)

    # 更新VM状态
    state = load_vm_state(vm)
    state["status"] = "idle"
    state["current_task"] = None
    state["tasks_completed"] += 1
    state["total_tokens_used"] += task["actual_tokens"]
    state["heartbeat"] = datetime.now().isoformat()
    save_vm_state(vm, state)

    log(f"[{vm}]  完成: {task['task_id']} (实际token: {task['actual_tokens']})")
    return {"task_id": task["task_id"], "status": "completed", "tokens": task["actual_tokens"]}

if __name__ == "__main__":
    vm = sys.argv[1] if len(sys.argv) > 1 else "vm1"
    task_id = sys.argv[2] if len(sys.argv) > 2 else None
    project = sys.argv[3] if len(sys.argv) > 3 else "demo-project"

    if task_id:
        task = load_task(task_id, project)
        result = execute(task, vm)
        print(json.dumps(result, ensure_ascii=False))
    else:
        # 无任务时自动轮询
        print(json.dumps({"status": "idle", "vm": vm, "message": "等待任务派发..."}, ensure_ascii=False))
