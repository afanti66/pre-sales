#!/usr/bin/env python3
"""mermaid→drawio→PNG 管线脚本
   mermaid代码→drawio XML (可手动编辑优化)→PNG导出"""
import os, json, subprocess, re, base64, xml.etree.ElementTree as ET

NFS = "/home/afanti/projects/sales-agent-dashboard/nfs-data/projects/user-management"
MERMAID_DIR = f"{NFS}/artifacts/design/mermaid-drafts"
DRAWIO_DIR = f"{NFS}/artifacts/design/drawio-src"
PNG_DIR = f"{NFS}/artifacts/design/png-output"

os.makedirs(MERMAID_DIR, exist_ok=True)
os.makedirs(DRAWIO_DIR, exist_ok=True)
os.makedirs(PNG_DIR, exist_ok=True)

# ===== 从各章节提取mermaid代码 =====
chapters = {
    "需求全景图": f"{NFS}/artifacts/design/001_requirement.md",
    "总体架构图": f"{NFS}/artifacts/design/002_architecture.md",
    "服务模块关系图": f"{NFS}/artifacts/design/003_subproject.md",
    "SSO认证时序图": f"{NFS}/artifacts/design/004_common.md",
}

extracted = {}
for name, path in chapters.items():
    if not os.path.exists(path):
        print(f"  ⚠️  {name}: 文件不存在")
        continue
    with open(path) as f:
        content = f.read()
    # 提取 ```mermaid ... ``` 块
    blocks = re.findall(r'```mermaid\n(.+?)```', content, re.DOTALL)
    if blocks:
        extracted[name] = blocks
        print(f"  ✅ {name}: {len(blocks)} 个mermaid块")
    else:
        print(f"  ⚠️  {name}: 未找到mermaid代码")

# ===== 保存mermaid草稿到独立文件 =====
for name, blocks in extracted.items():
    for i, block in enumerate(blocks):
        fn = f"{name.replace(' ', '_')}_{i+1}.mmd"
        safe_name = re.sub(r'[^\w\-_.]', '', fn)
        with open(f"{MERMAID_DIR}/{safe_name}", 'w') as f:
            f.write(block)
        print(f"  💾 已保存: {safe_name}")

# ===== 生成drawio XML框架 =====
def gen_drawio_xml(diagram_name, mermaid_text):
    """将mermaid代码包装为drawio格式的XML"""
    escaped_text = mermaid_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # drawio XML模板（空画布，mermaid文本标注在图形中）
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="sales-agent-pipeline" version="24.0">
  <diagram id="{diagram_name}" name="{diagram_name}">
    <mxGraphModel dx="0" dy="0" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="827" pageHeight="1169" math="0" shadow="0">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        <mxCell id="2" value="{escaped_text}" style="text;html=1;strokeColor=none;fillColor=#F5F7FA;fontSize=12;fontFamily=Microsoft YaHei;align=left;verticalAlign=top;whiteSpace=wrap;overflow=hidden;rounded=1;" vertex="1" parent="1">
          <mxGeometry x="20" y="20" width="780" height="1100" as="geometry"/>
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>'''

# ===== 生成drawio文件 =====
for name, blocks in extracted.items():
    for i, block in enumerate(blocks):
        safe_name = re.sub(r'[^\w\-_.]', '', f"{name.replace(' ', '_')}_{i+1}.drawio")
        xml = gen_drawio_xml(f"{name}_{i+1}", block)
        with open(f"{DRAWIO_DIR}/{safe_name}", 'w', encoding='utf-8') as f:
            f.write(xml)

print(f"\n{'='*60}")
print(f"管线就绪:")
print(f"  mermaid草稿: {MERMAID_DIR}/")
print(f"  drawio源文件: {DRAWIO_DIR}/")
print(f"  PNG输出: {PNG_DIR}/")
print(f"\n手动步骤（在drawio桌面版中）：")
print(f"  1. 打开 drawio-desktop")
print(f"  2. File → Open → {DRAWIO_DIR}/xxx.drawio")
print(f"  3. 使用模板优化布局，添加配色和样式")
print(f"  4. File → Export As → PNG → 保存至 {PNG_DIR}/")
