#!/usr/bin/env python3
"""环境自检：GPU / 驱动 / torch / ComfyUI / 关键节点 / 关键模型是否齐备。

用法:
  # 本机
  python check_env.py --host 127.0.0.1 --port 8188
  # 局域网另一台（只查服务侧；torch 版本需在目标机本地跑）
  python check_env.py --host <局域网IP> --port 8188
  # 指定 ComfyUI 安装目录（默认自动探测）
  python check_env.py --comfy-dir "D:/ComfyUI/ComfyUI_windows_portable"

只读检查，不修改任何东西。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request

NEEDED_NODES = [
    "UNETLoader", "VAELoader", "CLIPLoader", "UpscaleModelLoader",
    "DLSS5Settings", "DLSS5EnhanceImages", "SeedVR2VideoUpscaler",
    "SeedVR2LoadDiTModel", "ReferenceLatent", "Flux2Scheduler",
]
NEEDED_MODELS = {
    "diffusion_models": ["flux-2-klein-9b-fp8.safetensors", "flux-2-klein-4b-fp8.safetensors"],
    "text_encoders": ["qwen_3_8b_fp8mixed.safetensors", "qwen_3_4b.safetensors"],
    "vae": ["flux2-vae.safetensors"],
    "upscale_models": ["1x-ReFocus-V3.pth", "4x-UltraSharp\\4x-UltraSharp.pth"],
}


def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def detect_comfy_dir():
    """自动定位 ComfyUI 安装目录（优先环境变量 COMFYUI_PATH）。"""
    cands = []
    env = os.environ.get("COMFYUI_PATH")
    if env:
        cands.append(env)
    cands += [
        r"C:\ComfyUI\ComfyUI_windows_portable",
        r"D:\ComfyUI\ComfyUI_windows_portable",
        r"C:\ComfyUI_windows_portable",
        r"D:\ComfyUI_windows_portable",
        os.path.expanduser("~/ComfyUI_windows_portable"),
    ]
    for c in cands:
        if c and os.path.isdir(os.path.join(c, "python_embeded")):
            return c
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1", help="本机用 127.0.0.1，局域网填对方 IP")
    ap.add_argument("--port", type=int, default=8188)
    ap.add_argument("--comfy-dir", default="", help="ComfyUI 安装目录，留空自动探测")
    args = ap.parse_args()
    base = f"http://{args.host}:{args.port}"
    problems = []

    print("== 本机 GPU / 驱动 ==")
    exe = shutil.which("nvidia-smi") or r"C:\Windows\System32\nvidia-smi.exe"
    try:
        full = subprocess.run([exe], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30).stdout
        out = subprocess.run([exe, "--query-gpu=name,driver_version,memory.total",
                              "--format=csv,noheader"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30).stdout.strip()
        print("  ", out or "(nvidia-smi 无输出)")
        for line in full.splitlines():
            if "CUDA UMD Version" in line:
                print("   ", line.strip(), "（需 ≥ 13.0 才能启用 cu130 优化路径）")
    except Exception as e:
        print("   nvidia-smi 失败:", e)
        problems.append("未检测到 nvidia-smi")

    print("== PyTorch（装在 ComfyUI 嵌入式 Python 里）==")
    comfy_dir = args.comfy_dir or detect_comfy_dir()
    if not comfy_dir:
        print("   未自动定位到 ComfyUI 安装目录；用 --comfy-dir 指定，或设置环境变量 COMFYUI_PATH")
        problems.append("未找到 ComfyUI 安装目录，跳过 torch 版本检查")
        comfy_dir = ""
    py = os.path.join(comfy_dir, "python_embeded", "python.exe") if comfy_dir else ""
    if py and os.path.exists(py):
        code = ("import torch;print(torch.__version__, torch.version.cuda, "
                "torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda')")
        r = subprocess.run([py, "-c", code], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        print("  ", r.stdout.strip() or r.stderr.strip()[:200])
        if "cu13" not in r.stdout:
            problems.append("PyTorch 不是 cu130 版本：fp8 权重加载会崩溃（见 references/troubleshooting.md）")
    else:
        if comfy_dir:
            print("   未找到嵌入式 Python:", py)
            problems.append("找不到 ComfyUI 嵌入式 Python")

    print("== ComfyUI 服务 ==")
    try:
        stats = get(base + "/system_stats")
        print("   ComfyUI", stats["system"]["comfyui_version"],
              "| torch", stats["system"].get("pytorch_version"))
        devs = stats.get("devices", [])
        for d in devs:
            print("   ", d.get("name"), f"{(d.get('vram_total',0)-d.get('vram_free',0))/1e9:.1f}GB used")
    except Exception as e:
        print("   连接失败:", e)
        problems.append(f"ComfyUI 未响应 {base}")
        print("\n结论: 有问题, 见上。")
        return

    print("== 关键节点 ==")
    oi = get(base + "/object_info")
    for n in NEEDED_NODES:
        ok = n in oi
        print(f"   {'OK ' if ok else 'MISS'} {n}")
        if not ok:
            problems.append(f"缺少节点 {n}")

    print("== 关键模型 ==")
    for folder, files in NEEDED_MODELS.items():
        loader = {"diffusion_models": "UNETLoader", "text_encoders": "CLIPLoader",
                  "vae": "VAELoader", "upscale_models": "UpscaleModelLoader"}[folder]
        try:
            key = ("unet_name" if folder == "diffusion_models"
                   else "clip_name" if folder == "text_encoders"
                   else "vae_name" if folder == "vae" else "model_name")
            v = oi[loader]["input"]["required"][key]
            first = v[0]
            if isinstance(first, dict):
                opts = first.get("options", [])
            elif isinstance(first, str) and len(v) > 1 and isinstance(v[1], dict):
                opts = v[1].get("options", [])   # COMBO 形式: ["COMBO", {"options": [...]}]
            elif isinstance(first, list):
                opts = first
            else:
                opts = []
        except Exception:
            opts = []
        for f in files:
            hit = any(f.lower() in str(o).lower() for o in opts)
            print(f"   {'OK ' if hit else 'MISS'} {folder}/{f}")
            if not hit:
                problems.append(f"缺模型 {folder}/{f}")

    print("\n== 结论 ==")
    if problems:
        for p in problems:
            print("   [!]", p)
    else:
        print("   全部就绪，三条管线均可运行。")


if __name__ == "__main__":
    main()
