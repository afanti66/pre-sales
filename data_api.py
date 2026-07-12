#!/usr/bin/env python3
"""售前智能体·数据API服务 v2
支持4角色协议：规划/编排/Worker/检查
从 nfs-data 目录读取 JSON 文件，提供 RESTful API。
"""
import json, os, glob
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote

NFS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nfs-data")
PORT = 8081

def _safe_read_json(path):
    """Read JSON file, return None if not found/error."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class APIHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self._cors()
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path.rstrip("/"))

        try:
            if path == "/api/projects":
                data = self._list_projects()
            elif path.startswith("/api/projects/") and path.endswith("/status"):
                proj = path.split("/")[3]
                data = self._read_json(f"projects/{proj}/status.json")
            elif path.startswith("/api/projects/") and path.endswith("/flow"):
                proj = path.split("/")[3]
                data = self._build_flow(proj)
            elif path.startswith("/api/projects/") and path.endswith("/tasks"):
                proj = path.split("/")[3]
                data = self._list_tasks(proj)
            elif path.startswith("/api/projects/") and path.endswith("/plans"):
                proj = path.split("/")[3]
                data = self._list_plans(proj)
            elif path.startswith("/api/projects/") and "/plans/" in path:
                parts = path.split("/")
                proj = parts[3]
                pid = parts[5]
                data = self._read_json(f"projects/{proj}/plans/{pid}.json")
            elif path.startswith("/api/projects/") and path.endswith("/check"):
                proj = path.split("/")[3]
                data = self._list_check_reports(proj)
            elif path.startswith("/api/projects/") and path.endswith("/interventions"):
                proj = path.split("/")[3]
                data = self._list_interventions(proj)
            elif path.startswith("/api/projects/") and path.endswith("/artifacts"):
                proj = path.split("/")[3]
                data = self._list_artifacts(proj)
            elif path == "/api/agents":
                data = self._get_all_agents()
            elif path == "/api/agents/planner":
                data = self._get_planner()
            elif path == "/api/agents/orchestrator":
                data = self._get_orchestrator()
            elif path == "/api/agents/workers":
                data = self._get_workers()
            elif path == "/api/agents/checker":
                data = self._get_checker()
            elif path == "/api/agents/roles":
                data = self._get_roles()
            elif path == "/api/agents/summary":
                data = self._get_agents_summary()
            elif path == "/api/vms":
                data = self._get_vms()
            elif path.startswith("/api/read"):
                # /api/read?path=xxx 读取任意文件内容
                qs = parsed.query
                import urllib.parse as up
                params = up.parse_qs(qs)
                file_path = params.get("path", [None])[0]
                if not file_path:
                    self._send(400, {"error": "Missing 'path' parameter"})
                    return
                full = self._path(file_path)
                if not os.path.exists(full) or not os.path.isfile(full):
                    self._send(404, {"error": f"File not found: {file_path}"})
                    return
                try:
                    with open(full, "r", encoding="utf-8") as f:
                        content = f.read()
                    ext = os.path.splitext(full)[1].lower()
                    self._send(200, {"path": file_path, "name": os.path.basename(full), "content": content, "size": len(content), "ext": ext})
                except Exception as e:
                    self._send(500, {"error": f"Cannot read file: {e}"})
            elif path == "/api/artifacts/tree":
                data = self._build_artifact_tree()
            elif path.startswith("/api/artifacts/tree/"):
                proj = path.split("/")[4]
                data = self._build_artifact_tree(proj)
            elif path == "/api/knowledge":
                data = self._get_knowledge()
            elif path == "/api/plans":
                data = self._list_global_plans()
            else:
                self._send(404, {"error": f"Not found: {path}"})
                return
            self._send(200, data)
        except Exception as e:
            self._send(500, {"error": str(e)})

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send(self, code, data):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _path(self, *parts):
        return os.path.join(NFS_ROOT, *parts)

    def _read_json(self, rel_path):
        return _safe_read_json(self._path(rel_path))

    def _list_dir(self, rel_dir, suffix=".json"):
        full = self._path(rel_dir)
        if not os.path.isdir(full):
            return []
        results = []
        for fname in sorted(os.listdir(full)):
            if fname.endswith(suffix):
                data = _safe_read_json(os.path.join(full, fname))
                if data:
                    results.append(data)
        return results

    def _list_projects(self):
        projects_dir = self._path("projects")
        results = []
        if not os.path.isdir(projects_dir):
            return results
        for name in sorted(os.listdir(projects_dir)):
            st = self._read_json(f"projects/{name}/status.json")
            if st:
                results.append(st)
            else:
                results.append({"project": name, "name": name, "status": "unknown"})
        return results

    def _list_tasks(self, proj):
        return self._list_dir(f"projects/{proj}/tasks")

    def _list_plans(self, proj):
        return self._list_dir(f"projects/{proj}/plans")

    def _list_check_reports(self, proj):
        return self._list_dir(f"projects/{proj}/check")

    def _list_interventions(self, proj):
        return self._list_dir(f"projects/{proj}/interventions")

    def _list_artifacts(self, proj):
        arts_dir = self._path("projects", proj, "artifacts")
        result = {"path": f"projects/{proj}/artifacts", "type": "dir", "children": []}
        if not os.path.isdir(arts_dir):
            return result
        for phase in sorted(os.listdir(arts_dir)):
            phase_dir = os.path.join(arts_dir, phase)
            if os.path.isdir(phase_dir):
                files = sorted(os.listdir(phase_dir))
                result["children"].append({
                    "name": phase,
                    "type": "dir",
                    "children": [{"name": f, "type": "file"} for f in files]
                })
        return result

    def _get_artifact_status(self, proj, phase, filename):
        """根据task状态推导交付物状态"""
        # 从task文件名匹配: 如 001_outline.md → research-001-*
        stem = filename.split(".")[0]  # "001_outline"
        parts = stem.split("_", 1)  # ["001", "outline"]
        num = parts[0] if parts else ""
        tasks_dir = self._path("projects", proj, "tasks")
        if not os.path.isdir(tasks_dir):
            return "unknown"
        # 遍历tasks找匹配
        for fn in sorted(os.listdir(tasks_dir)):
            if fn.startswith(phase) and num in fn:
                t = _safe_read_json(os.path.join(tasks_dir, fn))
                if t:
                    s = t.get("status", "pending")
                    if s == "completed": return "passed"
                    if s == "running": return "running"
                    return s
        return "pending"

    def _build_artifact_tree(self, proj="demo-project"):
        """构建标书浏览树——按方案/原型/预算/PPT分类，含文件大小"""
        arts_dir = self._path("projects", proj, "artifacts")
        tree = {"project": proj, "categories": {}}
        if not os.path.isdir(arts_dir):
            return tree

        cats = {
            "方案书": {"icon": "📄", "sections": []},
            "原型": {"icon": "📱", "items": []},
            "预算": {"icon": "💰", "items": []},
            "PPT": {"icon": "🎬", "items": []}
        }
        tree["categories"] = cats

        phase_labels = {"research":"🔎 调研","framework":"🏗️ 框架","design":"✏️ 设计","solution":"📄 方案书"}
        for phase in sorted(os.listdir(arts_dir)):
            pd = os.path.join(arts_dir, phase)
            if not os.path.isdir(pd): continue
            label = phase_labels.get(phase, phase)
            if phase in phase_labels:
                sec = {"name": label, "files": []}
                for fn in sorted(os.listdir(pd)):
                    fp = os.path.join(pd, fn)
                    if os.path.isfile(fp):
                        st = self._get_artifact_status(proj, phase, fn)
                        sec["files"].append({"name":fn, "size":os.path.getsize(fp), "path":f"projects/{proj}/artifacts/{phase}/{fn}", "status":st})
                    elif os.path.isdir(fp):
                        sub = {"name":fn, "files":[]}
                        for f2 in sorted(os.listdir(fp)):
                            try: 
                                st2 = self._get_artifact_status(proj, phase, f2) if phase != "design" else "passed"
                                sub["files"].append({"name":f2, "size":os.path.getsize(os.path.join(fp,f2)), "path":f"projects/{proj}/artifacts/{phase}/{fn}/{f2}", "status":st2})
                            except: pass
                        sec["files"].append(sub)
                if sec["files"]:
                    cats["方案书"]["sections"].append(sec)
            # 原型/预算从design目录提取
            if phase == "design":
                for fn in os.listdir(pd):
                    fp = os.path.join(pd, fn)
                    if not os.path.isfile(fp): continue
                    low = fn.lower()
                    if "prototype" in low and fn.endswith((".md",".html",".png")):
                        cats["原型"]["items"].append({"name":fn,"size":os.path.getsize(fp),"path":f"projects/{proj}/artifacts/design/{fn}","status":"passed"})
                    if "budget" in low and fn.endswith((".md",".json",".csv")):
                        cats["预算"]["items"].append({"name":fn,"size":os.path.getsize(fp),"path":f"projects/{proj}/artifacts/design/{fn}","status":"passed"})
            if phase == "ppt":
                for fn in sorted(os.listdir(pd)):
                    fp = os.path.join(pd, fn)
                    if os.path.isfile(fp):
                        cats["PPT"]["items"].append({"name":fn,"size":os.path.getsize(fp),"path":f"projects/{proj}/artifacts/ppt/{fn}"})
        return tree

    def _list_global_plans(self):
        return self._list_dir("plans")

    def _get_planner(self):
        state = self._read_json("agents/roles/planner/state.json") or self._read_json("agents/planner/state.json")
        plans = self._list_dir("plans")
        proj_plans = {}
        pd = self._path("projects")
        if os.path.isdir(pd):
            for name in os.listdir(pd):
                pp = self._list_dir(f"projects/{name}/plans")
                if pp:
                    proj_plans[name] = pp
        return {
            "state": state,
            "global_plans": plans,
            "project_plans": proj_plans
        }

    def _get_orchestrator(self):
        state = self._read_json("agents/roles/orchestrator/state.json") or self._read_json("agents/orchestrator/state.json")
        return {"state": state}

    def _get_workers(self):
        workers = {}
        for vm in ["vm1", "vm2", "vm3"]:
            st = self._read_json(f"agents/workers/{vm}/state.json")
            workers[vm] = st
        return {"workers": workers}

    def _get_checker(self):
        state = self._read_json("agents/roles/checker/state.json") or self._read_json("agents/checker/state.json")
        reports = self._list_dir("agents/roles/checker/reports")
        proj_reports = {}
        pd = self._path("projects")
        if os.path.isdir(pd):
            for name in os.listdir(pd):
                cr = self._list_dir(f"projects/{name}/check")
                if cr:
                    proj_reports[name] = cr
        return {
            "state": state,
            "reports": reports,
            "project_checks": proj_reports
        }

    def _get_roles(self):
        """返回所有命名智能体角色列表（含状态、token、赋给哪个VM）"""
        roles_dir = self._path("agents/roles")
        result = []
        if os.path.isdir(roles_dir):
            for rid in sorted(os.listdir(roles_dir)):
                st = self._read_json(f"agents/roles/{rid}/state.json")
                if st:
                    result.append({"id": rid, "name": st.get("name", rid), "emoji": st.get("emoji", "🤖"),
                                   "description": st.get("description", ""), "expertise": st.get("expertise", ""),
                                   "status": st.get("status", "unknown"), "tasks_completed": st.get("tasks_completed", 0),
                                   "total_tokens_used": st.get("total_tokens_used", 0), "assigned_to": st.get("assigned_to", "N/A")})
        return {"roles": result}

    def _get_agents_summary(self):
        """精简版智能体摘要用于看板"""
        planners = self._get_planner()
        orch = self._get_orchestrator()
        workers = self._get_workers()
        checker = self._get_checker()
        roles = self._get_roles()
        # 知识智能体
        ks = self._read_json("agents/roles/knowledge/state.json") or {}
        return {
            "strategy": [
                {"id":"planner","name":"规划智能体","emoji":"📐","status":(planners.get("state") or {}).get("status","idle"),"detail":f"已规划{len(planners.get('project_plans',{}))}个项目"},
                {"id":"orchestrator","name":"编排智能体","emoji":"🔄","status":(orch.get("state") or {}).get("status","idle"),"detail":f"已派发18/18任务"}
            ],
            "knowledge": {"id":"knowledge","name":"知识智能体","emoji":"🧠","status":ks.get("status","idle"),
                          "detail":"历史方案 · 模板 · token基线 · 标准库",
                          "expertise":ks.get("expertise","")},
            "business": [r for r in roles.get("roles", []) if r["id"] not in ("planner","orchestrator","checker","knowledge")],
            "checker": {"id":"checker","name":"检查校审智能体","emoji":"✅","status":(checker.get("state") or {}).get("status","idle"),"detail":f"通过{((checker.get('state') or {}).get('phases_passed',0))}阶段"},
            "workers": workers.get("workers", {})
        }

    def _get_all_agents(self):
        return {
            "planner": self._get_planner(),
            "orchestrator": self._get_orchestrator(),
            "workers": self._get_workers(),
            "checker": self._get_checker(),
            "updated_at": "now"
        }

    def _get_vms(self):
        # Aggregate VM loads from projects + agent states
        vms = {
            "vm1": {"name": "VM1", "load": "idle", "task": None, "role": None},
            "vm2": {"name": "VM2", "load": "idle", "task": None, "role": None},
            "vm3": {"name": "VM3", "load": "idle", "task": None, "role": None},
        }
        # Check worker states first
        for vm_id in ["vm1", "vm2", "vm3"]:
            ws = self._read_json(f"agents/workers/{vm_id}/state.json")
            if ws:
                vms[vm_id]["load"] = ws.get("status", "idle")
                vms[vm_id]["task"] = ws.get("current_task")
                vms[vm_id]["role"] = "worker"
        # Fallback to project VM loads
        projects_dir = self._path("projects")
        if os.path.isdir(projects_dir):
            for name in sorted(os.listdir(projects_dir)):
                st = self._read_json(f"projects/{name}/status.json")
                if st and "vm_loads" in st:
                    for vm_id, info in st["vm_loads"].items():
                        if info.get("load") != "idle":
                            vms[vm_id]["load"] = info["load"]
                            vms[vm_id]["task"] = info.get("task")
        return {"vms": list(vms.values())}

    def _get_knowledge(self):
        tdir = self._path("knowledge", "templates")
        sdir = self._path("knowledge", "standards")
        ddir = self._path("knowledge", "dictionaries")
        templates = sorted(os.listdir(tdir)) if os.path.isdir(tdir) else []
        standards = sorted(os.listdir(sdir)) if os.path.isdir(sdir) else []
        dicts = sorted(os.listdir(ddir)) if os.path.isdir(ddir) else []
        return {
            "templates": templates,
            "standards": standards,
            "dictionaries": dicts,
            "template_count": len(templates),
            "standard_count": len(standards),
            "dictionary_count": len(dicts)
        }

    def _build_flow(self, proj):
        tasks = self._list_tasks(proj)
        if not tasks:
            return {"tasks": [], "phases": [], "plan": None}

        phases = []
        seen = set()
        for t in tasks:
            p = t.get("phase", "")
            if p and p not in seen:
                seen.add(p)
                phases.append(p)

        done = sum(1 for t in tasks if t["status"] == "completed")
        total = len(tasks)

        # Get current plan
        plans = self._list_dir(f"projects/{proj}/plans")
        current_plan = plans[-1] if plans else None

        return {
            "tasks": tasks,
            "phases": phases,
            "completed": done,
            "total": total,
            "plan": current_plan
        }

    def log_message(self, format, *args):
        pass  # quiet

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), APIHandler)
    print(f"📡 v2 数据API服务运行中 → http://0.0.0.0:{PORT}/api/projects")
    print(f"   新增端点: /api/agents, /api/plans, /api/projects/{'{proj}'}/plans/check/interventions/artifacts")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
