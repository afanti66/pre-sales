# Pre-Sales Agent Pipeline Dashboard

售前智能体管线看板系统。基于 **Hermes Agent** + **NFS事件驱动** 的多VM智能体系统，从招标调研到方案书PPT，全流程可视化管控。

## 系统架构

```
┌─ 导航区 ──────────────────────────────────────┐
│ ⚡ 售前智能体系统 │ v1.0 │ [项目·阶段·完成数]  │
├──────┬───────────────────────┬─────────────────┤
│📊项目│ 🔧流程                │ 📊面板          │
│[阶段]│ [节点域] [时空域]     │ [团队] [算力]   │
│[标书]│                       │                 │
│      │ D3拓扑图(三层架构)    │ 14智能体/3VM   │
│      │ D3甘特图(三条线)      │                 │
├──────┴───────────────────────┴─────────────────┤
│ © 2026 · Nous Research Hermes                 │
└────────────────────────────────────────────────┘
```

### 三层架构
- **📐 策略层**：规划 → 编排（总控调度）
- **🔧 业务层**：调研 → 框架 → 4并行设计 → 2串行 → 汇总 → PPT
- **✅ 质控层**：检查校审（全链条边界对齐）

## 快速启动

```bash
# 1. 启动数据API服务
python3 data_api.py &

# 2. 启动看板（浏览器访问）
python3 -m http.server 8080
# 访问 http://localhost:8080
```

## NFS事件驱动管线

系统基于NFS目录状态变迁驱动智能体调度：

```
调研 → 规划 → 编排 → 框架(需求矩阵→业务框架→系统框架→背景知识)
 → 设计(4并行: 需求/总体/分项/公共 → 2串行: 原型/预算 → 汇总: 图例)
 → 方案书(DOCX) → PPT
```

- **14个独立智能体**：各司其职，模板化输出
- **3台VM并行**：分布式锁（mkdir原子性）
- **自检+外部检查**：双保险质量保障
- **每阶段推送**：检查通过后立即推送到案卷

## 项目结构

```
├── index.html          # D3.js看板（拓扑图+甘特图+四向折叠）
├── data_api.py         # 数据API服务（agents/roles/artifacts/tree）
├── gen_promo_video.py  # 宣传视频生成器
├── lib/
│   └── d3.v7.min.js    # D3.js v7.9.0
├── nfs-data/
│   ├── projects/       # 项目数据
│   │   ├── demo-project/
│   │   └── user-mgmt/
│   ├── knowledge/
│   │   └── templates/  # 14个独立模板
│   └── agents/         # 智能体脚本
└── promo-dashboard.mp4 # 看板宣传视频
```

## 宣传视频

<video src="https://raw.githubusercontent.com/afanti66/pre-sales/main/promo-dashboard.mp4" controls width="100%" style="max-width:720px;border-radius:8px;">
  您的浏览器不支持视频播放，请 <a href="./promo-dashboard.mp4">下载 MP4 文件</a>。
</video>

## 技术栈

- **前端**：纯HTML/CSS/JS + D3.js v7（拓扑力导向图+甘特时间轴）
- **后端**：Python HTTP API（CORS支持）
- **调度**：NFS事件驱动 + 排他性文件锁
- **输出**：DOCX方案书 + PPT演示文稿 + drawio/PNG图表
