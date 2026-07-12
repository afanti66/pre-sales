#!/usr/bin/env python3
"""售前智能体管线·看板宣传视频生成器"""
import os, sys, time, subprocess, json, shutil, math

FPS = 10
W, H = 1280, 720
OUTPUT = os.path.expanduser("~/promo-dashboard.mp4")
SCR_DIR = os.path.expanduser("~/promo-frames")
os.makedirs(SCR_DIR, exist_ok=True)

# ===== 步骤定义 =====
# 每个步骤：操作 + 停留秒数 + 字幕文本（None=不显示）
STEPS = [
    # === 开场：顶部导航 【4s】===
    {"action": "idle", "duration": 4.0,
     "narration": "售前智能体管线看板，从招标调研到方案书PPT，全流程可视化管控。"},

    # === 拓扑图全景 【5s】===
    {"action": "scroll_to", "selector": "#topology-svg", "duration": 5.0,
     "narration": "拓扑图展示三层架构：策略层负责规划编排，业务层承载调研框架设计等十个核心节点，质控层全程检查校审。"},

    # === 滚动查看底部 【3s】===
    {"action": "scroll", "pixels": 250, "duration": 3.0,
     "narration": "垂直布局完整展示从规划到检查校审的十三级业务流水线。"},

    # === 点击弹出节点详情 【4s】===
    {"action": "click", "selector": "#topology-svg svg g.topo-node", "index": 3, "duration": 4.0,
     "narration": "单击任意节点，弹出阶段详情弹窗，进度状态任务清单一目了然。"},

    # === 关闭弹窗 【2s】===
    {"action": "close_modal", "duration": 2.0,
     "narration": None},

    # === 折叠左面板 【3s】===
    {"action": "toggle_panel", "side": "left", "duration": 3.0,
     "narration": "左面板折叠，看板自动适配宽屏布局，拓扑图重新居中绘制。"},

    # === 展开左面板+折叠右面板 【3s】===
    {"action": "toggle_panel", "side": "left", "duration": 1.0, "narration": None},
    {"action": "toggle_panel", "side": "right", "duration": 3.0,
     "narration": "右面板折叠，内容区进一步扩展，展示自适应布局能力。"},

    # === 展开右面板，切甘特图 【3s】===
    {"action": "toggle_panel", "side": "right", "duration": 1.0, "narration": None},
    {"action": "switch_tab", "tab": "gantt", "duration": 4.0,
     "narration": "切换至时空域视图，三条业务流按统一时间轴展开，阶段状态实时着色。"},

    # === 点击甘特查看任务 【4s】===
    {"action": "click_gantt_task", "duration": 3.0,
     "narration": "甘特图展示每条流的子任务进度，已完成待开始状态一目了然。"},

    # === 切回拓扑 【3s】===
    {"action": "switch_tab", "tab": "topology", "duration": 3.0,
     "narration": "节点域与时空域双视图切换，从不同维度审视管线运行状态。"},
]

# ===== Playwright 操作 =====
def take_screenshot(page, path):
    page.screenshot(path=path, full_page=False)

def run():
    from playwright.sync_api import sync_playwright

    frame_idx = 0
    all_frames = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-gpu", "--window-size=1280,720"]
        )
        context = browser.new_context(
            viewport={"width": W, "height": H},
            locale="zh-CN",
            device_scale_factor=1
        )
        page = context.new_page()

        # DASHBOARD_URL
        DASHBOARD = "http://192.168.2.9:8080/"

        # 先导航到看板并等待渲染
        print("  导航到看板...")
        try:
            page.goto(DASHBOARD, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)  # 等JS执行和拓扑图渲染
            # 验证页面是否加载成功
            title = page.title()
            print(f"  页面标题: {title}")
            # 检查SVG是否存在
            has_svg = page.evaluate("!!document.querySelector('#topology-svg svg')")
            print(f"  拓扑图渲染: {'是' if has_svg else '否'}")
        except Exception as e:
            print(f"  导航失败: {e}")

        for si, step in enumerate(STEPS):
            action = step["action"]
            dur = step["duration"]
            n_frames = max(1, int(dur * FPS))

            print(f"[{si+1}/{len(STEPS)}] {action} ({dur}s → {n_frames}帧)")

            if action == "title":
                # 生成看板背景色标题帧
                for fi in range(n_frames):
                    fp = os.path.join(SCR_DIR, f"frame_{frame_idx:06d}.png")
                    subprocess.run([
                        "ffmpeg", "-y",
                        "-f", "lavfi", "-i", f"color=c=#0d1117:s={W}x{H}:d=0.04",
                        "-frames:v", "1", fp
                    ], capture_output=True, timeout=10)
                    all_frames.append(fp)
                    frame_idx += 1
                continue

            # 所有非title步骤: 先确保看板已加载
            if si == 2:  # 第一个真正的截图步骤前，导航到看板
                try:
                    page.goto(DASHBOARD, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(2)
                except:
                    pass

            if action == "idle":
                for fi in range(n_frames):
                    fp = os.path.join(SCR_DIR, f"frame_{frame_idx:06d}.png")
                    page.screenshot(path=fp)
                    all_frames.append(fp)
                    frame_idx += 1
                continue

            if action == "scroll_to":
                # 确保元素可见
                try:
                    page.evaluate(f"document.querySelector('{step['selector']}')?.scrollIntoView()")
                    time.sleep(0.3)
                except:
                    pass
                for fi in range(n_frames):
                    fp = os.path.join(SCR_DIR, f"frame_{frame_idx:06d}.png")
                    page.screenshot(path=fp)
                    all_frames.append(fp)
                    frame_idx += 1
                continue

            if action == "scroll":
                for fi in range(n_frames):
                    fp = os.path.join(SCR_DIR, f"frame_{frame_idx:06d}.png")
                    if fi == 0:
                        page.evaluate(f"window.scrollBy(0, {step['pixels']})")
                        time.sleep(0.2)
                    page.screenshot(path=fp)
                    all_frames.append(fp)
                    frame_idx += 1
                continue

            if action == "click":
                try:
                    # 先切到拓扑图tab
                    page.evaluate("switchTab('topology', document.querySelector('.tab-btn'))")
                    time.sleep(0.8)
                    sel = step["selector"]
                    idx = step.get("index", 0)
                    els = page.query_selector_all(sel)
                    if idx < len(els):
                        els[idx].click()
                        time.sleep(0.5)
                except Exception as e:
                    print(f"  click error: {e}")
                for fi in range(n_frames):
                    fp = os.path.join(SCR_DIR, f"frame_{frame_idx:06d}.png")
                    page.screenshot(path=fp)
                    all_frames.append(fp)
                    frame_idx += 1
                continue

            if action == "close_modal":
                try:
                    page.evaluate("closeModal()")
                    time.sleep(0.3)
                except:
                    pass
                for fi in range(n_frames):
                    fp = os.path.join(SCR_DIR, f"frame_{frame_idx:06d}.png")
                    page.screenshot(path=fp)
                    all_frames.append(fp)
                    frame_idx += 1
                continue

            if action == "toggle_panel":
                side = step["side"]
                try:
                    if side == "left":
                        page.evaluate("togglePanel('left')")
                    else:
                        page.evaluate("togglePanel('right')")
                    time.sleep(0.5)
                except:
                    pass
                for fi in range(n_frames):
                    fp = os.path.join(SCR_DIR, f"frame_{frame_idx:06d}.png")
                    page.screenshot(path=fp)
                    all_frames.append(fp)
                    frame_idx += 1
                continue

            if action == "switch_tab":
                tab = step["tab"]
                try:
                    btn = page.query_selector(f"button[onclick*='{tab}']")
                    if btn:
                        btn.click()
                    else:
                        page.evaluate(f"switchTab('{tab}')")
                    time.sleep(1.0)
                except:
                    pass
                for fi in range(n_frames):
                    fp = os.path.join(SCR_DIR, f"frame_{frame_idx:06d}.png")
                    page.screenshot(path=fp)
                    all_frames.append(fp)
                    frame_idx += 1
                continue

            if action == "click_gantt_task":
                try:
                    page.evaluate("switchTab('gantt', document.querySelectorAll('.tab-btn')[1])")
                    time.sleep(1.0)
                except:
                    pass
                for fi in range(n_frames):
                    fp = os.path.join(SCR_DIR, f"frame_{frame_idx:06d}.png")
                    page.screenshot(path=fp)
                    all_frames.append(fp)
                    frame_idx += 1
                continue

        browser.close()

    print(f"共截取 {len(all_frames)} 帧")
    return all_frames


# ===== 合成视频 =====
def render_video(frame_paths, output_path):
    """用 concat demuxer 合成视频"""
    print("合成视频...")
    concat_file = os.path.join(SCR_DIR, "frames_concat.txt")

    # 最后一帧停留加倍
    frame_paths_adj = list(frame_paths)
    if len(frame_paths_adj) > 1:
        frame_paths_adj.append(frame_paths_adj[-1])  # 多停留一次

    with open(concat_file, "w") as f:
        for fp in frame_paths_adj:
            f.write(f"file '{fp}'\nduration {1/FPS:.4f}\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        "-preset", "medium",
        "-crf", "18",
        output_path
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print("ffmpeg error:", r.stderr[-500:])
        return False
    print(f"视频已生成: {output_path}")
    return True


def add_bgm(video_path, output_path, volume=0.12):
    """添加背景音乐（视频无音轨时直接附加）"""
    print("添加背景音乐...")
    bgm_path = os.path.join(SCR_DIR, "bgm.mp3")

    # 生成5秒C大调和弦循环
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=f=261.63:d=5:r=44100,volume=0.15",
        "-f", "lavfi", "-i", "sine=f=329.63:d=5:r=44100,volume=0.10",
        "-filter_complex", "[0:a][1:a]amix=inputs=2[a]",
        "-map", "[a]", "-b:a", "64k", "-t", "5", bgm_path
    ], capture_output=True, timeout=15)

    # 获取视频时长，循环BGM
    r = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", video_path
    ], capture_output=True, text=True, timeout=10)
    try:
        dur = float(r.stdout.strip())
    except:
        dur = 60.0

    # concat循环BGM
    bgm_concat = os.path.join(SCR_DIR, "bgm_concat.txt")
    n_loops = max(1, math.ceil(dur / 5))
    with open(bgm_concat, "w") as f:
        for _ in range(n_loops):
            f.write(f"file '{bgm_path}'\n")

    bgm_long = os.path.join(SCR_DIR, "bgm_long.mp3")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", bgm_concat,
        "-c", "copy", "-t", str(dur), bgm_long
    ], capture_output=True, timeout=30)

    # 视频无音轨，直接附加BGM
    r = subprocess.run([
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", bgm_long,
        "-filter_complex", f"[1:a]volume={volume}[a]",
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "96k",
        "-shortest", output_path
    ], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print("  add_bgm failed, copying raw:", r.stderr[-200:])
        shutil.copy2(video_path, output_path)
    print(f"最终视频: {output_path}")
    return True


if __name__ == "__main__":
    print("=" * 50)
    print("售前智能体管线·看板 宣传视频生成器")
    print("=" * 50)

    font_path = "/home/afanti/.fonts/notoserif/SubsetOTF/SC/NotoSerifSC-Medium.otf"
    if not os.path.exists(font_path):
        font_path = "/usr/share/fonts/truetype/arphic/uming.ttc"

    # 1. 先截图（基于步骤预设时长）
    raw_frames = run()
    FPS = 10

    # 2. 先生成所有解说音频→获取实际时长
    print("生成解说音频并测量实际时长...")
    audio_durations = []
    audio_files = []
    for si, step in enumerate(STEPS):
        dur = step.get("duration", 0.5)
        nar = step.get("narration", "")
        if nar:
            ap = os.path.join(SCR_DIR, f"narration_{si:02d}.mp3")
            print(f"  段{si}: {nar[:30]}...")
            r = subprocess.run(["edge-tts","--voice","zh-CN-XiaoxiaoNeural",
                "--text", nar, "--write-media", ap],
                capture_output=True, text=True, timeout=30)
            if r.returncode == 0 and os.path.getsize(ap) > 1000:
                audio_files.append(ap)
                # ffprobe取实际时长
                r2 = subprocess.run(["ffprobe","-v","error","-show_entries",
                    "format=duration","-of","default=noprint_wrappers=1:nokey=1",ap],
                    capture_output=True, text=True, timeout=10)
                try:
                    actual_dur = float(r2.stdout.strip())
                except:
                    actual_dur = dur
                audio_durations.append(actual_dur)
                print(f"    实际{actual_dur:.1f}s(预设{dur:.0f}s)")
            else:
                print(f"    失败,用静音{step['duration']}s")
                silent = os.path.join(SCR_DIR, f"silent_{si:02d}.mp3")
                subprocess.run(["ffmpeg","-y","-f","lavfi","-i",
                    f"anullsrc=r=44100:cl=mono:d={dur}","-b:a","64k",silent],
                    capture_output=True, timeout=10)
                audio_files.append(silent)
                audio_durations.append(dur)
        else:
            # 无解说步：静音
            silent = os.path.join(SCR_DIR, f"silent_{si:02d}.mp3")
            if not os.path.exists(silent):
                subprocess.run(["ffmpeg","-y","-f","lavfi","-i",
                    f"anullsrc=r=44100:cl=mono:d={dur}","-b:a","64k",silent],
                    capture_output=True, timeout=10)
            audio_files.append(silent)
            audio_durations.append(dur)

    # 3. 帧重抽样：按实际音频时长调整帧数
    print("帧重抽样同步音画...")
    adjusted_frames = []
    frame_idx = 0
    old_durs = [s.get("duration", 0.5) for s in STEPS]
    for si in range(len(STEPS)):
        actual_dur = audio_durations[si]
        n_frames = max(1, int(actual_dur * FPS))
        # 从raw_frames中取该步骤的原始帧
        start_f = sum(int(old_durs[i]*FPS) for i in range(si))
        end_f = start_f + int(old_durs[si]*FPS)
        seg = raw_frames[start_f:end_f]
        if not seg:
            seg = [raw_frames[-1]] if raw_frames else []
        # 重抽样到n_frames
        for fi in range(n_frames):
            si2 = min(int(fi * len(seg) / max(n_frames, 1)), len(seg)-1)
            adjusted_frames.append(seg[si2])

    print(f"  调整后: {len(adjusted_frames)}帧 (原{len(raw_frames)}帧)")

    # 4. 用调整后的帧合成视频
    raw_video = os.path.join(SCR_DIR, "raw.mp4")
    if not render_video(adjusted_frames, raw_video):
        sys.exit(1)

    # 5. 拼接音频（按实际时长）
    audio_concat = os.path.join(SCR_DIR, "audio_concat.txt")
    with open(audio_concat, "w") as f:
        for ap in audio_files:
            f.write(f"file '{ap}'\n")
    mixed_audio = os.path.join(SCR_DIR, "mixed_audio.mp3")
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0",
        "-i", audio_concat, "-c", "copy", mixed_audio],
        capture_output=True, timeout=30)

    # 6. 叠加解说文字（用实际音频时长计算时间轴）
    print("叠加解说文字...")
    cum_time = 0.0
    drawtext_filters = []
    for si, step in enumerate(STEPS):
        actual_dur = audio_durations[si]
        nar = step.get("narration", "")
        if nar:
            safe_text = nar.replace("'", "'\\\\''").replace(":", "\\\\:").replace(",", "\\\\,")
            drawtext_filters.append(
                f"drawtext=text='{safe_text}'"
                f":fontfile={font_path}"
                f":fontsize=20:fontcolor=white"
                f":x=(w-text_w)/2:y=h-70"
                f":box=1:boxcolor=black@0.5:boxborderw=12"
                f":enable='between(t,{cum_time:.2f},{cum_time+actual_dur:.2f})'"
            )
        cum_time += actual_dur

    filter_str = ",\n".join(drawtext_filters)
    print(f"  总时长: {cum_time:.1f}s")

    subprocess.run(["ffmpeg","-y","-i", raw_video, "-i", mixed_audio,
        "-map", "0:v", "-map", "1:a",
        "-vf", filter_str,
        "-c:v", "libx264", "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart", "-shortest", OUTPUT],
        capture_output=True, text=True, timeout=120)

    print(f"\n✅ 宣传视频已生成: {OUTPUT}")
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1",OUTPUT],
        capture_output=True, text=True, timeout=10)
    print(f"   时长: {float(r.stdout.strip()):.1f}秒" if r.stdout.strip() else "")
