#!/usr/bin/env python3
"""
售前智能体 · Worker子代理 (Worker Agent)
职责：执行原子任务 → 用自己的64K完成 → 写回NFS
用法：
  python3 worker.py run <project> <task_id>              # 执行指定任务
  python3 worker.py run-all <project> <phase> [vm]       # 执行指定VM上某阶段所有就绪任务
  python3 worker.py status <project> <task_id>           # 查看任务状态
  python3 worker.py reset <project> <task_id>            # 重置任务为pending
"""
import json, os, sys, glob, shutil
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

def _get_worker_state(vm_id="vm1"):
    ws = _read_json(os.path.join(NFS_ROOT, "agents", "workers", vm_id, "state.json"))
    if not ws:
        ws = {
            "vm_id": vm_id,
            "status": "idle",
            "current_task_id": None,
            "token_used_total": 0,
            "token_used_current": 0,
            "task_history": [],
        }
    return ws

def _save_worker_state(vm_id, state):
    _write_json(os.path.join(NFS_ROOT, "agents", "workers", vm_id, "state.json"), state)


TASK_LIBRARY = {
    "research-outline": {
        "description": "根据需求文档生成方案大纲",
        "prompt": """你是一个售前方案专家。请根据以下需求文档生成一份完整的方案大纲。
- 输出格式：markdown
- 包含章节目录（一级~三级）
- 每章标注预期内容要点
请输出完整大纲。""",
    },
    "research-literature": {
        "description": "整理参考文献中的关键知识",
        "prompt": """你是一个文献分析专家。请阅读以下参考文献，提取关键知识点。
- 分条目整理
- 标注来源
- 给出知识要点和应用建议""",
    },
    "research-solution": {
        "description": "根据需求整理方案知识",
        "prompt": """你是一个售前方案专家。请根据需求文档提炼方案相关知识。
- 关键需求 → 对应方案要点
- 技术路线选择
- 行业对标分析""",
    },
    "framework-matrix": {
        "description": "生成需求矩阵",
        "prompt": """你是一个需求分析专家。请根据调研产出生成需求矩阵。
- 业务需求 → 功能需求 → 非功能需求对应关系表
- 优先级标注（P0/P1/P2）
- 可选的验证指标""",
    },
    "framework-business": {
        "description": "生成业务框架",
        "prompt": """你是一个架构师。请根据方案大纲生成业务框架。
- 业务角色和用例
- 业务流程
- 业务实体关系""",
    },
    "framework-system": {
        "description": "生成系统框架",
        "prompt": """你是一个系统架构师。请根据业务框架和方案大纲设计系统框架。
- 系统模块划分
- 模块间接口关系
- 技术栈选型建议""",
    },
    "design-requirement": {
        "description": "编写方案书需求分析章节",
        "prompt": """你是一个售前方案专家。请编写方案书的「需求分析」章节。
- 结合需求矩阵和原始需求
- 分功能需求/性能需求/接口需求/安全需求
- 每个需求项给出量化指标
- 输出mermaid草稿图（流程图/用例图）""",
    },
    "design-overall": {
        "description": "编写方案书总体方案章节",
        "prompt": """你是一个系统架构师。请编写方案书的「总体方案」章节。
- 系统总体架构图描述
- 设计原则和设计约束
- 逻辑架构 vs 物理架构
- 输出mermaid草稿图（架构图/部署图）""",
    },
    "design-module": {
        "description": "编写方案书分项方案章节",
        "prompt": """你是一个技术专家。请编写方案书的「分项方案」章节。
- 每个模块的详细设计
- 模块内关键流程
- 接口详细说明
- 输出mermaid草稿图（时序图/类图）""",
    },
    "design-common": {
        "description": "编写方案书公共部分章节",
        "prompt": """你是一个售前方案专家。请编写方案书的「公共部分」章节。
- 安全方案
- 运维方案
- 项目管理方案
- 培训方案""",
    },
    "design-prototype": {
        "description": "编写方案书原型设计章节",
        "prompt": """你是一个UX设计师。请编写方案书的「原型设计」章节。
- 核心界面设计
- 交互流程设计
- 输出ASCII原型示意""",
    },
    "design-budget": {
        "description": "编写方案书预算方案章节",
        "prompt": """你是一个项目预算专家。请编写方案书的「预算方案」章节。
- 硬件/软件/服务费用估算
- 人力成本估算
- 总体预算表""",
    },
    "design-diagram": {
        "description": "图例汇总：标准化并转drawio+PNG",
        "prompt": """你是一个方案配图专家。请执行以下工作：
1. 收齐各子节点的mermaid草稿图
2. 统一编号体系（图1-1到图x-y）
3. 统一风格（配色/线型/字体）
4. 跨章节校验一致性（同一模块在不同章节的图是否一致）
5. 输出drawio格式定义
6. 描述每张图的PNG插入位置（方案书对应章节）""",
    },
}

def read_task(project, task_id):
    return _read_json(os.path.join(NFS_ROOT, "projects", project, "tasks", f"{task_id}.json"))

def write_task(project, task_id, data):
    _write_json(os.path.join(NFS_ROOT, "projects", project, "tasks", f"{task_id}.json"), data)

def read_artifacts(project, paths):
    """读取任务输入产出"""
    contents = {}
    for path in (paths or []):
        full_path = os.path.join(NFS_ROOT, "projects", project, path)
        if os.path.isfile(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                contents[path] = f.read()
        elif os.path.isdir(full_path):
            for fname in sorted(os.listdir(full_path)):
                fp = os.path.join(full_path, fname)
                if os.path.isfile(fp):
                    with open(fp, "r", encoding="utf-8") as f:
                        contents[f"{path}/{fname}"] = f.read()
    return contents

def write_artifact(project, rel_path, content):
    """写入产出物"""
    full_path = os.path.join(NFS_ROOT, "projects", project, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    return rel_path


def execute_task(project, task_id, vm_id="vm1"):
    """执行一个任务（模拟Worker执行）"""
    task = read_task(project, task_id)
    if not task:
        print(f"❌ 任务 {task_id} 不存在")
        return False

    if task["status"] == "done":
        print(f"⏭️ 任务 {task_id} 已完成，跳过")
        return True

    ttype = task.get("type", "research-outline")
    lib = TASK_LIBRARY.get(ttype)
    if not lib:
        print(f"❌ 未知任务类型: {ttype}")
        return False

    # 更新Worker状态
    ws = _get_worker_state(vm_id)
    ws["status"] = "running"
    ws["current_task_id"] = task_id
    _save_worker_state(vm_id, ws)

    # 标记任务开始
    task["status"] = "running"
    task["started_at"] = datetime.now().isoformat()
    write_task(project, task_id, task)

    print(f"⚡ Worker({vm_id}) 执行任务: {task_id} ({task['name']})")
    print(f"   类型: {ttype} | 预估token: {task.get('estimated_tokens', '?')}")
    print(f"   描述: {lib['description']}")

    # 读取输入
    inputs = read_artifacts(project, task.get("input_files", []))
    if inputs:
        print(f"   输入文件: {', '.join(inputs.keys())}")
    else:
        print(f"   无输入文件（或使用动态产出）")

    # ===== 模拟Worker产出 =====
    # 真实场景下这里是调用LLM (Hermes delegate_task) 生成内容
    # 模拟模式下生成示范内容
    out_phase = task.get("phase", "unknown")
    out_filename = task_id.replace(f"{out_phase}-", "").replace("-", "_")

    generated = f"""# {task['name']}

## 概述
本文档由Worker子代理 ({vm_id}) 自动生成。
任务ID: {task_id}
生成时间: {datetime.now().isoformat()}

## 内容
本{lib['description']}文档。
根据项目需求和已有输入文件生成。

## 输出约束
- 格式: markdown
- 字数: ~2000字
- 适用阶段: {out_phase}

---

*此内容为模拟产出，真实运行时由LLM生成*
"""

    # 如果是mermaid相关的，添加示范mermaid
    if "mermaid" in lib['description'] or ttype in ["design-requirement", "design-overall", "design-module"]:
        generated += f"""

## Mermaid草图

```mermaid
graph TD
    A[功能模块] --> B[子模块1]
    A --> C[子模块2]
    B --> D[接口A]
    C --> E[接口B]
    D --> F[外部系统]
    E --> F
```
"""

    # 写入产出
    out_dir = f"artifacts/{out_phase}"
    out_path = f"{out_dir}/{out_filename}.md"
    written_path = write_artifact(project, out_path, generated)

    # 更新mermaid产出路径（用于图例汇总）
    mermaid_out = f"{out_dir}/{out_filename}_mermaid.md"

    # 如果是设计阶段的子节点，额外写mermaid文件
    if out_phase == "design" and "diagram" not in task_id:
        mermaid_content = f"""# {task['name']} - Mermaid草稿

```mermaid
graph TD
    {task_id.replace('-', '_')}[{task['name']}]
    --> Sub1[子功能A]
    --> Sub2[子功能B]
    Sub1 --> Inter[接口C]
    Sub2 --> Inter
    Inter --> Ext[外部服务]
```
"""
        write_artifact(project, mermaid_out, mermaid_content)

    # ===== 自检 =====
    self_check_passed = True
    check_result = {"content_check": "通过", "format_check": "通过", "notes": None}

    # 更新任务状态
    task["status"] = "done"
    task["completed_at"] = datetime.now().isoformat()
    task["result_summary"] = {
        "output_files": [out_path, mermaid_out] if out_phase == "design" and "diagram" not in task_id else [out_path],
        "token_used": task.get("estimated_tokens", 0),
        "self_check": check_result,
    }
    task["output_files"] = task["result_summary"]["output_files"]
    write_task(project, task_id, task)

    # 更新Worker状态
    ws = _get_worker_state(vm_id)
    ws["status"] = "idle"
    ws["current_task_id"] = None
    ws["token_used_total"] += task.get("estimated_tokens", 0)
    ws["token_used_current"] = 0
    ws["task_history"] = ws.get("task_history", []) + [{
        "task_id": task_id,
        "completed_at": task["completed_at"],
        "estimated_tokens": task.get("estimated_tokens", 0),
    }]
    _save_worker_state(vm_id, ws)

    print(f"\n✅ 任务完成: {task_id}")
    print(f"   产出: {written_path}")
    print(f"   自检: {'✅通过' if self_check_passed else '❌失败'}")
    print(f"   Token: {task.get('estimated_tokens', 0)}")

    return True


def run_all(project, phase, vm_filter=None):
    """执行某VM上某阶段所有pending任务"""
    tasks_dir = os.path.join(NFS_ROOT, "projects", project, "tasks")
    if not os.path.isdir(tasks_dir):
        print(f"❌ 无任务目录")
        return

    tasks = []
    for fname in sorted(os.listdir(tasks_dir)):
        if fname.endswith(".json"):
            t = _read_json(os.path.join(tasks_dir, fname))
            if t and t.get("phase") == phase and t["status"] == "pending":
                if vm_filter and t.get("vm") != vm_filter:
                    continue
                # 检查依赖
                deps_ready = True
                for dep in t.get("dependencies", []):
                    dt = _read_json(os.path.join(tasks_dir, f"{dep}.json"))
                    if not dt or dt["status"] != "done":
                        deps_ready = False
                        break
                if deps_ready:
                    tasks.append(t)

    if not tasks:
        print(f"⏳ {phase}/{vm_filter or 'all'}: 无就绪任务")
        return

    print(f"📋 即将执行 {len(tasks)} 个任务 ({phase}/{vm_filter or 'all'})")
    for t in tasks:
        print(f"  - {t['task_id']} ({t['name']})")

    for t in tasks:
        vm = t.get("vm", vm_filter or "vm1")
        if vm_filter:
            ok = execute_task(project, t["task_id"], vm)
        else:
            ok = execute_task(project, t["task_id"], vm)
        if not ok:
            print(f"❌ 任务 {t['task_id']} 失败，停止批量执行")
            break


def show_task_status(project, task_id):
    task = read_task(project, task_id)
    if not task:
        print(f"❌ 任务 {task_id} 不存在")
        return

    print(f"📋 任务: {task_id} ({task.get('name', '?')})")
    print(f"   状态: {task['status']}")
    print(f"   阶段: {task.get('phase', '?')}")
    print(f"   VM: {task.get('vm', '?')}")
    print(f"   类型: {task.get('type', '?')}")
    print(f"   依赖: {task.get('dependencies', [])}")
    print(f"   输入文件: {task.get('input_files', [])}")
    print(f"   产出: {task.get('output_files', [])}")
    if task.get("started_at"): print(f"   开始: {task['started_at']}")
    if task.get("completed_at"): print(f"   完成: {task['completed_at']}")
    if task.get("result_summary"):
        rs = task["result_summary"]
        if rs.get("self_check"):
            print(f"   自检: {rs['self_check']}")


def reset_task(project, task_id):
    task = read_task(project, task_id)
    if not task:
        print(f"❌ 任务 {task_id} 不存在")
        return
    task["status"] = "pending"
    task["started_at"] = None
    task["completed_at"] = None
    task["result_summary"] = None
    task["output_files"] = []
    write_task(project, task_id, task)
    print(f"🔄 任务 {task_id} 已重置为pending")


def main():
    if len(sys.argv) < 3:
        print("用法:")
        print("  python3 worker.py run <project> <task_id> [vm]")
        print("  python3 worker.py run-all <project> <phase> [vm]")
        print("  python3 worker.py status <project> <task_id>")
        print("  python3 worker.py reset <project> <task_id>")
        sys.exit(1)

    cmd = sys.argv[1]
    project = sys.argv[2]

    if cmd == "run":
        if len(sys.argv) < 4:
            print("用法: python3 worker.py run <project> <task_id> [vm]")
            sys.exit(1)
        task_id = sys.argv[3]
        vm = sys.argv[4] if len(sys.argv) > 4 else "vm1"
        execute_task(project, task_id, vm)
    elif cmd == "run-all":
        if len(sys.argv) < 4:
            print("用法: python3 worker.py run-all <project> <phase> [vm]")
            sys.exit(1)
        phase = sys.argv[3]
        vm = sys.argv[4] if len(sys.argv) > 4 else None
        run_all(project, phase, vm)
    elif cmd == "status":
        if len(sys.argv) < 4:
            print("用法: python3 worker.py status <project> <task_id>")
            sys.exit(1)
        show_task_status(project, sys.argv[3])
    elif cmd == "reset":
        if len(sys.argv) < 4:
            print("用法: python3 worker.py reset <project> <task_id>")
            sys.exit(1)
        reset_task(project, sys.argv[3])
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
