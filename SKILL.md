---
name: archviz-render-enhancer
description: 建筑与室内效果图的 AI 增强工作流：FLUX2-Klein 语义重绘洗图、DLSS 5 神经渲染忠实增强、SeedVR2+ReFocus 高清细节增强三条管线，支持局域网多机分布式调度。
---

# 建筑效果图 AI 增强三管线

渲染图放大后发糊、材质像塑料、光影假、细节经不起推敲——这个 Skill 把三条互补的 AI 管线整理成可直接执行的 ComfyUI 工作流：**能重绘的、能保真的、能加细节的**，并支持把重绘任务分发到局域网里的第二台工作站。

## 何时用

- 建筑/室内/景观效果图放大后细节丢失、需要二次加工
- 需要"重出效果"（换光照氛围、换材质倾向）而不是"仅放大"
- 客户要求"画面不能动"，但要提升材质与纹理真实感
- 批量出图后统一做细节增强

## 环境要求

| 项 | 要求 |
|---|---|
| 显卡 | NVIDIA RTX 30/40/50 系（DLSS 5 管线需 RTX；4080/5070 实测通过） |
| 驱动 | 580 以上，CUDA UMD ≥ 13.0 |
| ComfyUI | 0.28+，建议 0.38.x |
| PyTorch | **必须是 cu130 及以上**（cu126 下加载 fp8 权重会触发 Windows "page error" 崩溃，见 references/troubleshooting.md） |
| Python | 3.12（Windows portable 自带嵌入式环境即可） |
| 存储 | 模型放 NVMe；机械盘随机读不足 1MB/s，会让模型加载慢到无法忍受 |

**模型清单**（约 31GB，均为 fp8/bf16 量化版）：

- `flux-2-klein-9b-fp8.safetensors`（重绘主力）+ `flux-2-klein-4b-fp8.safetensors`（快速草稿）
- `qwen_3_8b_fp8mixed.safetensors`（9B 配对文本编码器）+ `qwen_3_4b.safetensors`（4B 配对）
- `flux2-vae.safetensors`
- `1x-ReFocus-V3.pth`（细节增强）+ `4x-UltraSharp.pth`（通用放大）
- SeedVR2 权重 `seedvr2_ema_3b_fp8_e4m3fn.safetensors`（首次运行自动下载）

## 三条管线

| 管线 | 做什么 | 画面变化 | 典型耗时 | 用在什么时候 |
|---|---|---|---|---|
| **A. FLUX2-Klein 语义重绘** | 用参考潜空间重绘整张图 | 光照/材质/氛围都可能变 | 冷启 130s，热缓存 5s | 想要"重新出效果"，能接受画面变化 |
| **B. DLSS 5 神经渲染增强** | NVIDIA 神经渲染模型做保真增强 | **只加细节，不动构图与光照** | 单张 20–50s | 客户要求不改画；实景照片转效果图质感 |
| **C. SeedVR2 + ReFocus** | 生成式超分 + 1x 细节重建 | 纹理锐度提升，结构不变 | 单张 30–90s | 常规高清放大，纹理/边缘要"实" |

三条可以串联：**A 重绘 → B 增强 → C 细节**，也可以只用其中一条。

### A. FLUX2-Klein 语义重绘（`workflows/pipeline_a_flux2_rewrite.json`）

节点链路：`LoadImage → VAEEncode → ReferenceLatent（结构锚定）→ CFGGuider(cfg=1) → SamplerCustomAdvanced(euler, 4 步) → VAEDecode → 放大`

关键参数与用法：

- **提示词要写"约束 + 诉求"**，例如：「一张写实场景的建筑渲染图，严格保持画面中的构图、角度。使材质更细腻，场景具有电影叙事感。」
- `ReferenceLatent` 是保结构的关键；`cfg=1`、`euler`、4 步是 Flux2-Klein 蒸馏模型的推荐配置
- 4B 草稿 / 9B 出图是同一套节点只换模型名
- 放大建议：`4x-UltraSharp` 拉到 4x 后再缩到目标尺寸（避免放大后再缩的糊）

### B. DLSS 5 神经渲染增强（`workflows/pipeline_b_dlss5_enhance.json`）

节点链路：`LoadImage → DLSS5 Settings → DLSS5 Enhance Images → SaveImage`

- `upscaling_mode`：`1x (DLAA / native)` 原分辨率增强、`1.5x (Quality)`、`2x (Performance)`、`3x (Ultra Performance)`
- `nr_style`：`Natural` 贴近原图、`Cinematic` 力度更大
- `dlss_model_preset`：默认 `M`（纹理重建最强），`J/K` 更柔
- `local_structure_strength` 默认 1.5，是 AI 生成素材的甜点值
- 节点默认开启 `verify_neural_rendering`：如果 ReShade 日志里没有签名过的 feature-18 执行就直接报错，**不会拿普通放大冒充神经渲染**

### C. SeedVR2 + ReFocus（`workflows/pipeline_c_hd_detail.json`）

节点链路：`LoadImage → SeedVR2LoadDiTModel/LoadVAEModel → SeedVR2VideoUpscaler → 1x-ReFocus-V3 → SaveImage`

- SeedVR2 吃 IMAGE 批次（可直接喂单张图），`resolution` 是**短边目标像素**（图 1536×672，想 2x 就填 1344）
- `color_correction`：`wavelet`（默认，细节保留好）、`adain`、`lab`、`hsv`
- 1x-ReFocus-V3 是 1x 模型：尺寸不变，只重建皮肤/织物/边缘细节
- SeedVR2 权重首次运行自动下载，落盘位置即模型目录

## 快速开始

```bash
# 0) 环境自检（GPU/驱动/torch/模型/节点 一次查清）
python scripts/check_env.py --host 127.0.0.1 --port 8188

# 1) 提交一条管线并等结果
python scripts/queue_workflow.py --host 127.0.0.1 --port 8188 \
  --workflow workflows/pipeline_a_flux2_rewrite.json \
  --input "C:/path/to/render.png" --save-dir ./out

# 2) 生成三联/四联对比图
python scripts/make_comparison.py --out compare.png \
  --image "A=原图.png" --image "B=DLSS5.png" --image "C=FLUX2.png" \
  --crop 480,320
```

`queue_workflow.py` 会自动完成：上传输入图到 ComfyUI `input/` → 替换工作流里的 `LoadImage` 文件名 → POST `/prompt` → 轮询 `/history` → 把结果图下载到 `--save-dir`。

## 局域网分布式（本机或任意局域网 ComfyUI）

**这个 Skill 不绑定任何机器或地址**——`--host` 指向哪台 ComfyUI 都可以：本机写 `127.0.0.1`，
局域网写对方 IP，端口默认 8188（ComfyUI 可用 `--port` 改）。

两台机器时，重绘这种重活可以派给第二台：

```bash
# 本机 ComfyUI
python scripts/queue_workflow.py --host 127.0.0.1 --port 8188 \
  --workflow workflows/pipeline_a_flux2_rewrite.json --input render.png --save-dir ./out

# 局域网另一台（把 IP 换成你自己的）
python scripts/queue_workflow.py --host <局域网IP> --port 8188 \
  --workflow workflows/pipeline_a_flux2_rewrite.json --input render.png --save-dir ./out
```

被调用方需以 `--listen 0.0.0.0 --port 8188` 启动 ComfyUI；两台机的模型与自定义节点要对齐，
缺节点会报 `missing node type`。推荐分工：**RTX 50 那台做重绘/生成，RTX 40 这台做 DLSS5 增强与放大**。

安全提醒：ComfyUI 的 HTTP 接口**没有鉴权**，一旦 `--listen 0.0.0.0` 就是整个局域网可提交任务。
内部网络可用，**不要做公网端口映射**；需要收紧时用防火墙规则限定来源 IP。

## 调优速查

| 想要 | 调什么 |
|---|---|
| 重绘更保守 | 提示词里加强"严格保持构图/结构"，或换 4B 草稿先看效果 |
| 重绘更"电影感" | 提示词加"电影叙事感/电影级打光"；或管线 B 的 `nr_style=Cinematic` |
| 放大后别糊 | 先 4x-UltraSharp 再缩放；SeedVR2 用 `color_correction=wavelet` |
| 细节太夸张 | `local_structure_strength` 降到 1.0–1.2；`nr_intensity` 降到 0.8 以下往原图回混 |
| 画面发灰/色偏 | SeedVR2 换 `color_correction=adain` 或 `lab` |

## 注意事项

- **DLSS 5 节点是社区非官方实现**（MIT 许可，封装 NVIDIA 的 DLSS 5 运行时 + ReShade + RenoDX），与 NVIDIA 无官方关联；NVIDIA 官方的 DLSS 5 实时路径目前面向 RTX 50 系，离线图像路径由社区运行时覆盖 30/40/50 系
- 商用前确认各模型自身的许可条款（FLUX2-Klein、SeedVR2、ReFocus 均有各自授权说明）
- 本 Skill 的工作流默认使用 `cfg=1`、固定种子，结果可复现；批量跑时把 `RandomNoise` 的 `control` 改为 `randomize` 换取多样性

## 深入阅读

- `references/environment.md` —— 硬件/盘位实测、cu130 修复、双机拓扑
- `references/troubleshooting.md` —— fp8 崩溃、Reconnecting、缺失模型、加载慢等常见故障
- `references/pipeline-notes.md` —— 三条管线的实测数据与选型建议
