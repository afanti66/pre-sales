#!/usr/bin/env python3
"""检查智能体 - 内容检查 + 校审技能"""
import json, os, sys, re
from datetime import datetime

NFS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nfs-data")

def check_phase(project, phase):
    """对某个阶段的产出进行全面检查（内容+校审）"""
    check = {
        "check_id": f"check-{phase}-{project}",
        "phase": phase,
        "status": "running",
        "checked_by": "checker-001",
        "checked_at": datetime.now().isoformat(),
        "content_check": {"status": "passed", "issues": [], "completeness": 100},
        "proofreading": {"status": "passed", "issues": [], "corrections_made": 0},
        "delivery_artifacts": [],
        "rework_targets": []
    }

    # 检查规划方案
    plan_path = os.path.join(NFS, f"projects/{project}/plans/current.json")
    if os.path.exists(plan_path):
        with open(plan_path) as f:
            plan = json.load(f)

    # 检查该阶段所有completed任务
    tasks_dir = os.path.join(NFS, f"projects/{project}/tasks")
    phase_tasks = []
    if os.path.exists(tasks_dir):
        for fn in sorted(os.listdir(tasks_dir)):
            if fn.startswith(phase):
                with open(os.path.join(tasks_dir, fn)) as f:
                    t = json.load(f)
                    phase_tasks.append(t)

    completed = [t for t in phase_tasks if t["status"] == "completed"]
    failed = [t for t in phase_tasks if t["status"] == "failed"]

    if failed:
        check["status"] = "failed"
        check["rework_targets"] = [t["task_id"] for t in failed]
        check["content_check"]["status"] = "failed"
        check["content_check"]["issues"].append({
            "severity": "critical",
            "description": f"{len(failed)}个任务执行失败",
            "location": ", ".join(t["task_id"] for t in failed)
        })

    # 校审：逐项检查产出物
    if completed:
        for t in completed:
            for ref in t.get("output_refs", []):
                out_path = os.path.join(NFS, ref["path"])
                if os.path.isdir(out_path):
                    # 跳过目录引用，先列出目录下文件
                    check["delivery_artifacts"].append(f"{ref['path']}/ (dir)")
                    continue
                if os.path.exists(out_path) and os.path.isfile(out_path):
                    # 读取内容做校审
                    with open(out_path) as f:
                        content = f.read()

                    # 校审项1：术语一致性检查
                    terms_to_check = ["用户管理", "身份认证", "统一", "SSO", "RBAC"]
                    missing_terms = [term for term in terms_to_check if term not in content]
                    for term in missing_terms:
                        check["proofreading"]["issues"].append({
                            "type": "terminology",
                            "description": f"缺少关键术语'{term}'",
                            "location": ref["path"],
                            "suggestion": f"考虑补充'{term}'相关描述"
                        })

                    # 校审项2：标题层级检查（## → ### → #### 层级连续性）
                    headings = re.findall(r'^(#{1,6})\s', content, re.MULTILINE)
                    if headings:
                        prev_level = 0
                        for h in headings:
                            level = len(h)
                            if level > prev_level + 1 and prev_level > 0:
                                check["proofreading"]["issues"].append({
                                    "type": "heading_level",
                                    "description": f"标题层级跳跃: {prev_level}→{level}",
                                    "location": ref["path"],
                                    "suggestion": f"在中间补充{prev_level+1}级标题"
                                })
                            prev_level = level

                    # 校审项3：图表引用检查
                    if "图 " in content or "图1" in content or "图 1" in content:
                        figs = re.findall(r'图\s*\d+', content)
                        if not any(f"图1" in content for f in figs):
                            check["proofreading"]["issues"].append({
                                "type": "figure_ref",
                                "description": "存在图片相关内容但未找到标准图号引用",
                                "location": ref["path"],
                                "suggestion": "使用'图1-X: 标题'格式统一编号"
                            })

                    check["delivery_artifacts"].append(ref["path"])

        # 如果有校审问题，标记但不一定fatal
        if check["proofreading"]["issues"]:
            critical_issues = [i for i in check["proofreading"]["issues"]]
            if any(i.get("type") in ["terminology", "figure_ref"] for i in critical_issues):
                check["proofreading"]["status"] = "minor_issues"
                # 自动修正标记
                check["proofreading"]["corrections_made"] = 0

    # 如果没大问题，标记passed
    pending = [t for t in phase_tasks if t["status"] == "pending"]
    running = [t for t in phase_tasks if t["status"] == "running"]

    if check["status"] == "running":
        if not pending and not running:
            check["status"] = "passed"
        else:
            check["status"] = "running"
            check["content_check"]["completeness"] = int(
                len(completed) / len(phase_tasks) * 100
            )

    return check

def save_check(project, check):
    p = os.path.join(NFS, f"projects/{project}/check/{check['phase']}-check.json")
    with open(p, "w") as f:
        json.dump(check, f, indent=2, ensure_ascii=False)

def push_delivery(project, phase, check):
    """检查通过后推送至后台文档"""
    if check["status"] != "passed":
        return {"status": "skipped", "reason": "检查未通过"}

    delivery_dir = os.path.join(NFS, f"projects/{project}/delivery/{phase}")
    version_path = os.path.join(delivery_dir, "VERSION.txt")

    # 版本递增
    version = 1
    if os.path.exists(version_path):
        with open(version_path) as f:
            existing = f.read().strip()
            if existing.startswith("v"):
                version = int(existing[1:]) + 1

    with open(version_path, "w") as f:
        f.write(f"v{version}")

    # 拷贝检查报告
    check_src = os.path.join(NFS, f"projects/{project}/check/{phase}-check.json")
    check_dst = os.path.join(delivery_dir, f"{phase}-check.json")
    if os.path.exists(check_src):
        with open(check_src) as f_src:
            with open(check_dst, "w") as f_dst:
                f_dst.write(f_src.read())

    return {"status": "pushed", "version": f"v{version}", "delivery_dir": delivery_dir}

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "check"
    project = sys.argv[2] if len(sys.argv) > 2 else "demo-project"
    phase = sys.argv[3] if len(sys.argv) > 3 else "research"

    if action == "check":
        check = check_phase(project, phase)
        save_check(project, check)
        print(json.dumps(check, indent=2, ensure_ascii=False))
    elif action == "push":
        check_path = os.path.join(NFS, f"projects/{project}/check/{phase}-check.json")
        if os.path.exists(check_path):
            with open(check_path) as f:
                check = json.load(f)
            result = push_delivery(project, phase, check)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(json.dumps({"status": "error", "reason": f"No check report for {phase}"}, ensure_ascii=False))
