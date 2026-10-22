# 图像真实感增强与放大

**完整使用手册 / THE COMPLETE USER MANUAL**

ComfyUI 三条管线 · 3 个 API 工作流 · 4 个脚本 · 20+ 次真实实测

---

## PREFACE · 序言

> 图像放大后发糊、材质像塑料，是效果图交付里最常见的返工点。本手册把这件事拆成三条彼此独立的管线：一条负责重绘，一条负责保真增强，一条负责生成式超分——并把各自的边界、代价与适用场景写清楚。

这份手册的所有参数与结论都来自真实跑通的管线：同一张建筑渲染图，分别送进 FLUX2-Klein 语义重绘、NVIDIA DLSS 5 神经渲染、SeedVR2 生成式超分，再把产物并排放在一起比较。手册里写的每一个秒数、每一个报错，都是那 20 多次真实推理留下的记录，不是从文档里抄来的。

三条管线共享同一套工作流文件与脚本，可以单独使用，也可以串联：先用重绘定下氛围，再用神经渲染补材质，最后用生成式超分收细节。脚本负责调度与出图，ComfyUI 负责推理，局域网里的第二台机器负责分担算力。

**PROJECT FACTS · 项目信息与技术规约**

| 项目 | 内容 |
|---|---|
| DEVELOPER / 编制方 | 有物建筑 · MeansGroup |
| TARGET PLATFORM / 运行平台 | ComfyUI 0.28+ · Windows / macOS / Linux |
| SCOPE / 体系规模 | 3 条管线 · 3 个 API 工作流 · 4 个脚本 |
| PIPELINE / 核心管线 | FLUX2-Klein · DLSS 5 · SeedVR2 + ReFocus |
| DOCUMENTATION / 源工作流 | 官方帮助文档 + 一线实测（20+ 次真实推理） |
| EDITORIAL / 编辑与编译 | by 有物建筑 · means.group · Edition 2026.10 |

## 目录 · NAVIGATION & ROAD MAP

- **第一章 · 概述与定位** — OVERVIEW & SCOPE
- **第二章 · 环境搭建与安装** — SETUP & INSTALLATION
- **第三章 · 三条管线详解** — PIPELINES IN DETAIL
- **第四章 · 工作流与脚本清单** — WORKFLOWS & SCRIPTS
- **第五章 · 局域网分布式调度** — DISTRIBUTED EXECUTION
- **第六章 · 典型工作流** — TYPICAL RECIPES
- **第七章 · 故障排除** — TROUBLESHOOTING
- **附录 A · 参数速查表** — APPENDIX A · QUICK REFERENCE
- **附录 B · 资源与清单** — APPENDIX B · RESOURCES

## 第一章 · 概述与定位

*OVERVIEW & SCOPE*

这个 Skill 提供三条可以在 ComfyUI 里直接执行的图像增强管线，针对建筑与室内效果图的「放大发糊、材质失真、氛围单一」三类典型问题。每条管线都封装为一个可复用的 API 工作流，附带参数说明、实测耗时与选型建议。

### OVERVIEW · 三条管线的分工

*同一张图，三种处理意图*  |  `SUMMARY`  |  1.1

- **功能**：把「洗图」拆成三种互不重叠的意图：改画面、加质感、提分辨率。
- **要点**：三者不是替代关系。真实项目里最常见的组合是 A 定氛围、B 补材质、C 收细节。

| 管线 | 做什么 | 画面是否改变 | 实测耗时（热缓存） | 典型用途 |
|---|---|---|---|---|
| A · FLUX2-Klein 语义重绘 | 参考潜空间锚定结构后重绘整张图 | 会改画面（光影/材质/氛围） | 约 5 秒 / 张 | 换白天与黄昏、换材质倾向、换氛围 |
| B · N卡 DLSS5 图像增强+放大 | NVIDIA 神经渲染做离线增强与放大 | 零漂移（构图与光照一像素不动） | 约 20-50 秒 / 张 | 客户要求「不许改画」，或实景照片转效果图质感 |
| C · SeedVR2 生成式超分 | 扩散式超分 + 1x 细节重建 | 会重绘细节（小物件/人物姿态） | 约 30-90 秒 / 张 | 大图放大、锐度优先、有纵深与虚化的场景 |

### SCOPE · 什么画面适合哪条管线

*选型对照*  |  `GUIDE`  |  1.2

- **功能**：按「客户允许你动多少」这个唯一问题选管线。
- **要点**：DLSS5 是三者中唯一保证零漂移的：它的输出保留原图的每一处构图、光照与几何，只补材质与纹理。如果交付物必须与原稿严格一致，只有它可用。
- **要点**：SeedVR2 名为超分，本质是生成模型：它会重画画面里的小物件、人物姿态甚至局部结构。锐度收益最大，风险也最大，交稿前务必让客户过目。

![FIG. 1 / 三条管线的真实输出（依次为 DLSS5 增强、FLUX2 重绘、SeedVR2 超分，均为实拍素材的管线产物）](pipelines_strip.png)

*FIG. 1 / 三条管线的真实输出（依次为 DLSS5 增强、FLUX2 重绘、SeedVR2 超分，均为实拍素材的管线产物）*

## 第二章 · 环境搭建与安装

*SETUP & INSTALLATION*

管线本身不挑机器，但有两处环境硬门槛：PyTorch 必须是 cu130 及以上，以及模型必须放在 SSD 上。这两条不满足，表现为「加载 fp8 模型直接崩溃」和「加载慢到无法忍受」。

### SETUP · 硬件与驱动要求

*最低可用环境*  |  `REQUIREMENT`  |  2.1

- **功能**：下表是本手册全部实测的机器配置。低于此配置不一定不能用，但需要自担风险。
- **步骤**：1. 用 NVIDIA App 检查驱动版本；2. 确认 ComfyUI 侧 torch 的 CUDA 版本；3. 模型目录必须是 SSD。
- **要点**：驱动 580 以上可满足 cu130 运行时；实测 610.88 稳定。

| 项目 | 最低要求 | 实测配置 | 说明 |
|---|---|---|---|
| 显卡 | NVIDIA RTX 20 系以上 | RTX 4080 16GB（主）/ RTX 5070 12GB（副） | DLSS5 离线运行时需 RTX 30/40/50 |
| 显存 | 8GB | 16GB / 12GB | 9B 权重与文本编码器会轮流驻留 |
| 驱动 | 580+ | 610.88 | 驱动自报 CUDA UMD 13.3，满足 cu130 运行时 |
| PyTorch | 2.11.0+cu130 | 2.11.0+cu130 | cu126 会在加载 fp8 时崩溃（见 7.1） |
| ComfyUI | 0.28+ | 0.38.2 | 需 comfy_api V3 节点 API |
| Python | 3.12 | 3.12.10（嵌入式） | Windows portable 自带，无需另装 |
| 存储 | SSD 放模型 | NVMe 1TB 放主安装 | 机械盘随机读 0.98MB/s，会把加载拖垮 |

### INSTALL · ComfyUI 主安装与模型摆放

*目录结构*  |  `LAYOUT`  |  2.2

- **功能**：主安装与热模型放 NVMe；低频模型留机械盘，用 extra_model_paths.yaml 挂载。
- **步骤**：1. 复制 portable 目录到 NVMe；2. 复制热模型到 models/ 对应子目录；3. 写挂载配置。
- **要点**：别把整个 58GB 模型库都搬走。热模型约 31GB，够日常；冷模型按需再挪。

```
主安装/    ComfyUI_windows_portable/   ← 程序、节点、Python 环境
  models/
    diffusion_models/  flux-2-klein-9b-fp8.safetensors   ← 热
                      flux-2-klein-4b-fp8.safetensors   ← 热
    text_encoders/     qwen_3_8b_fp8mixed.safetensors     ← 热
                      qwen_3_4b.safetensors              ← 热
    vae/               flux2-vae.safetensors              ← 热
    upscale_models/    1x-ReFocus-V3.pth                  ← 热
                      4x-UltraSharp/4x-UltraSharp.pth    ← 热
冷模型/  models/  ← extra_model_paths.yaml 挂载，按需再读
    text_encoders/     t5xxl×2, qwen_2.5_vl_7b（LTX-2 用）
    diffusion_models/  flux-2-klein-base-4b-fp8
    checkpoints/       hunyuan_3d_v2.1
```

### CONFIG · 冷模型挂载

*extra_model_paths.yaml*  |  `CONFIG`  |  2.3

- **功能**：把机械盘上的冷模型挂进 ComfyUI 的模型搜索路径，下拉框里能直接选到。
- **步骤**：1. 在 ComfyUI 根目录新建 extra_model_paths.yaml；2. 写入下列内容；3. 重启 ComfyUI。
- **要点**：路径用双反斜杠或正斜杠都可以；改完不用清缓存，重启即生效。

```
# ComfyUI/extra_model_paths.yaml
cold_models:
  base_path: F:\ComfyUI_models\
  checkpoints: checkpoints
  diffusion_models: diffusion_models
  text_encoders: text_encoders
  vae: vae
  loras: loras
  upscale_models: upscale_models
```

### UPGRADE · PyTorch cu130 升级

*最关键的一步*  |  `CRITICAL`  |  2.4

- **功能**：ComfyUI 0.28+ 把 fp8 权重运算交给了 comfy_kitchen，该组件要求 CUDA ≥ 13.0。cu126 环境下 fp8 加载会直接让进程消失。
- **步骤**：在 ComfyUI 嵌入式 Python 里执行：
- **要点**：版本必须锁到 2.11.0：torchaudio 在 cu130 上最高只到 2.11.0，torch 2.12+ 会配不到 torchaudio。升级不需要重启电脑，只需重启 ComfyUI 进程。
- **要点**：回滚很简单：把 +cu130 换成 +cu126 重装即可，模型文件无需重下。

```
python_embeded\python.exe -m pip install \
  torch==2.11.0+cu130 torchvision==0.26.0+cu130 torchaudio==2.11.0+cu130 \
  --index-url https://download.pytorch.org/whl/cu130

# 验证：启动日志里这一行应为 disabled: False
#   Found comfy_kitchen backend cuda: {..., 'disabled': False, ...}
```

### VERIFY · 一键校验环境

*check_env.py*  |  `CHECK`  |  2.5

- **功能**：一次性检查 GPU、驱动、torch、ComfyUI 版本、关键节点与关键模型是否齐备。
- **步骤**：python scripts/check_env.py --host 127.0.0.1 --port 8188
- **要点**：也可以指向局域网另一台：--host <局域网IP>，用于核对两台机器的节点/模型是否对齐。

## 第三章 · 三条管线详解

*PIPELINES IN DETAIL*

每条管线都是一个可独立执行的 API 工作流。节点链路、关键参数与代价如下，工作流文件见 workflows/ 目录。

### PIPELINE A · FLUX2-Klein 语义重绘

*换光照、换材质、换氛围*  |  `RE-DRAW`  |  3.1

- **功能**：用参考潜空间锚定原图结构，再按中文提示词把整张图重绘一遍。会改画面。
- **节点链路**：LoadImage → VAEEncode → ReferenceLatent → CFGGuider(cfg=1) → SamplerCustomAdvanced(euler, 4 步) → VAEDecode → 放大 → SaveImage
- **关键参数**：cfg=1；euler；steps=4（Klein 是蒸馏模型，加步数反而过曝发糊）；seed 固定可复现，随机化可换构图。
- **提示词**：写法是「约束 + 诉求」：先写必须保持的东西，再写想要的改变。例：一张写实场景的建筑渲染图，严格保持画面中的构图、角度。使材质更细腻，场景具有电影叙事感。
- **要点**：ReferenceLatent 是保结构的关键，删掉它画面会跑飞。4B 用于草稿、9B 用于终稿。
- **耗时**：冷启动约 133 秒（含 19GB 权重加载），热缓存约 5 秒/张。

### PIPELINE B · N卡 DLSS5 图像增强+放大

*只加材质，不动画面*  |  `UPSCALE`  |  3.2

- **功能**：调用 NVIDIA 的神经渲染模型做离线增强与放大，只补材质与纹理，构图与光照零漂移。
- **节点链路**：LoadImage → DLSS5 Settings → DLSS5 Enhance Images → SaveImage
- **关键参数**：upscaling_mode：1x(DLAA) 原分辨率增强、1.5x、2x(Performance)、3x；nr_style：Natural 贴近原图 / Cinematic 更强；dlss_model_preset：M 纹理最强、J/K 更柔；local_structure_strength：AI 素材甜点 1.5、真实照片 1.0 上下。
- **要点**：节点默认开启 verify_neural_rendering：若运行日志里没有签名过的 feature-18 执行，它会直接报错而不是悄悄降级成普通放大——这是判断「真跑了神经渲染」的护栏，别关。
- **要点**：社区封装的 DLSS 5 运行时，RTX 30/40/50 都能跑离线图像，对显卡型号不挑剔。
- **耗时**：单张约 20-50 秒，取决于分辨率；首次运行需约 4 秒拉起原生 worker。

### PIPELINE C · SeedVR2 生成式超分

*扩散式超分 + 1x 细节重建*  |  `UPSHRINK`  |  3.3

- **功能**：用扩散式视频超分模型放大图像，再串一个 1x 细节模型重建纹理。锐度最高，也最会「重画」。
- **节点链路**：LoadImage → SeedVR2LoadDiTModel / LoadVAEModel → SeedVR2VideoUpscaler → 1x-ReFocus-V3 → SaveImage
- **关键参数**：resolution 填目标短边像素（1536×672 想 2x 就填 1344）；color_correction：wavelet 细节保留最好，adain 更摄影感，none 偏色；DiT 模型首次运行自动下载约 3.4GB。
- **要点**：1x-ReFocus-V3 是 1x 模型：不放大，只重建皮肤/织物/边缘细节，务必放在最后一步。
- **要点**：它会重画小物件与人物姿态；室内与有纵深虚化的场景表现最好。
- **耗时**：单张约 30-90 秒，随输出面积线性增长。

## 第四章 · 工作流与脚本清单

*WORKFLOWS & SCRIPTS*

包内共 3 个 API 工作流与 4 个脚本，全部可直接命令行调用，不依赖 ComfyUI 图形界面的鼠标操作。

| 文件 | 类型 | 作用 | 关键参数 |
|---|---|---|---|
| workflows/pipeline_a_flux2_rewrite.json | 工作流 | FLUX2-Klein 语义重绘 | 9B/4B、steps、seed |
| workflows/pipeline_b_dlss5_enhance.json | 工作流 | DLSS5 增强与放大 | upscaling_mode、nr_style、preset |
| workflows/pipeline_c_hd_detail.json | 工作流 | SeedVR2 超分 + ReFocus 细节 | resolution、color_correction |
| scripts/queue_workflow.py | 脚本 | 上传图→替换输入→提交→轮询→取回成品 | --host --port --workflow --input --save-dir |
| scripts/make_comparison.py | 脚本 | 多图拼成对比图（可中心裁切做细节对比） | --image 标签=路径 --crop 宽,高 |
| scripts/check_env.py | 脚本 | 环境/节点/模型自检 | --host --comfy-dir |
| scripts/make_post_cards.py | 脚本 | 生成小红书风格发布图（封面/长图/四格） | --kind poster|stack|quad |

### QUICKSTART · 三步跑起来

*最小可用路径*  |  `HOW TO`  |  4.1

- **功能**：自检 → 跑一条管线 → 出对比图，全程三条命令。
- **步骤**：见下方代码块；把 --workflow 换成 workflows/ 里的对应文件即可换管线。
- **要点**：queue_workflow.py 会自动把 --input 指定的图片上传到目标 ComfyUI 的 input 目录，并替换工作流里的 LoadImage 文件名，所以工作流本身可以复用，不必手改。

```
# 1) 自检
python scripts/check_env.py --host 127.0.0.1 --port 8188

# 2) 跑管线（换 --workflow 即可切换 A/B/C）
python scripts/queue_workflow.py --host 127.0.0.1 --port 8188 \
  --workflow workflows/pipeline_b_dlss5_enhance.json \
  --input "C:/path/render.png" --save-dir ./out

# 3) 出对比图（--crop 做中心细节裁切）
python scripts/make_comparison.py --out compare.png \
  --image "A 原图=orig.png" --image "B DLSS5=out/dlss5.png" --crop 480,320
```

## 第五章 · 局域网分布式调度

*DISTRIBUTED EXECUTION*

两台机器时，把重绘这类重活派给第二台，本机负责交互、神经渲染与放大。

### TOPOLOGY · 拓扑与角色分工

*谁做什么*  |  `NETWORK`  |  5.1

- **功能**：主控机跑 ComfyUI 并操作界面；计算节点只开 HTTP 接口接任务。
- **步骤**：计算节点以 --listen 0.0.0.0 --port 8188 启动 ComfyUI；主控机用 --host <局域网IP> 派发。
- **要点**：两台机的自定义节点与模型要对齐，否则远端会报 missing node type。
- **要点**：ComfyUI 的 HTTP 接口没有鉴权：一旦 --listen 0.0.0.0，整个局域网都能提交任务、取走产物。只在内网用，不要做公网端口映射；需要收紧时用防火墙限定来源 IP。

```
# 计算节点（第二台）
python ComfyUI/main.py --listen 0.0.0.0 --port 8188

# 主控机派发到局域网另一台
python scripts/queue_workflow.py --host <局域网IP> --port 8188 \
  --workflow workflows/pipeline_a_flux2_rewrite.json \
  --input render.png --save-dir ./out
```

## 第六章 · 典型工作流

*TYPICAL RECIPES*

### RECIPE 1 · 单图三版对比

*给客户看差异*  |  `COMPARE`  |  6.1

- **功能**：同一张图跑三条管线，把四张产物（原图 + 三版）并排输出。
- **步骤**：1. 跑 A/B/C 三次（可并行派发到两台机器）；2. make_comparison.py 拼图；3. make_post_cards.py 出发布图。
- **要点**：对比图务必同裁切、同尺寸，否则差异会被缩放掩盖。

### RECIPE 2 · 批量夜跑洗图

*整目录出图*  |  `BATCH`  |  6.2

- **功能**：对 input 目录里的所有图依次跑一条管线，产物落到指定目录。
- **步骤**：写一个循环调用 queue_workflow.py 即可；脚本本身是单图接口，批处理由外层脚本负责。
- **要点**：先在 2-3 张图上验证参数，再开整批；夜跑前确认输出目录所在盘剩余空间。

### RECIPE 3 · 串联 A→B→C

*重绘→补材质→收细节*  |  `PIPELINE`  |  6.3

- **功能**：先重绘定下氛围，再用神经渲染补材质，最后用生成式超分收细节。
- **步骤**：A 的输出作为 B 的输入，B 的输出作为 C 的输入。
- **要点**：串联会放大每一步的改写倾向：先用 A 定大局，再用 B/C 收细节，不要反过来先超分再重绘（会把已做好的细节全部推翻）。

## 第七章 · 故障排除

*TROUBLESHOOTING*

### ERROR 1 · 加载 fp8 模型时进程瞬间消失

*Windows page error*  |  `CRASH`  |  7.1

- **现象**：ComfyUI 无 Python 堆栈直接退出，日志最后停在 MixedPrecisionOps 或 _quantized_apply。
- **根因**：comfy_kitchen 要求 CUDA ≥ 13.0，cu126 下走 eager 分发路径会触发访问违例。
- **处理**：按 2.4 升级到 torch 2.11.0+cu130 三件套；回滚即换回 cu126。
- **要点**：这不是模型文件坏了——同一批文件在另一台机器上跑得好好的。

### ERROR 2 · 页面一直显示 Reconnecting

*websocket 断线*  |  `UI`  |  7.2

- **现象**：浏览器标签页顶部横幅一直显示 Reconnecting。
- **处理**：确认服务在跑（curl /system_stats），然后 F5 刷新页面。
- **要点**：服务器重启后旧标签页不会自动重连，这是正常现象，不是故障。

### ERROR 3 · 提示缺失模型 1x-ReFocus-V3.pth

*模型没装*  |  `MISSING`  |  7.3

- **现象**：工作流校验报「缺失模型」，管线 C 跑不起来。
- **处理**：从 HuggingFace 的 notkenski/upscalers 仓库下载 1x-ReFocus-V3.pth（约 67MB），放进 models/upscale_models/；放完不用重启，模型列表会立刻刷新。
- **要点**：SeedVR2 的 3.4GB 权重不用手工下载，首次运行会自动拉取。

### ERROR 4 · 模型加载慢到无法忍受

*存储瓶颈*  |  `PERF`  |  7.4

- **现象**：同一张图冷启要几十分钟，热缓存后只要几秒。
- **根因**：模型在机械盘上。实测 NVMe 随机读 552MB/s，机械盘只有 0.98MB/s——模型加载是 safetensors 的 mmap 小块随机读，差距会被放大几百倍。
- **处理**：把热模型挪到 NVMe，冷模型用 extra_model_paths.yaml 挂载。
- **要点**：页面文件同样偏小（实测 8GB），建议扩到 32-64GB，但该改动需要重启才生效。

### ERROR 5 · DLSS5 报 worker 未在 60 秒内退出

*运行时收尾*  |  `NODE`  |  7.5

- **现象**：The native DLSS worker did not exit within 60 seconds and was killed。
- **处理**：只影响那一次任务，重跑即可；频繁出现就重启 ComfyUI。
- **要点**：该节点默认开启签名校验，遇到这个问题说明确实跑过原生 worker。

### ERROR 6 · 提交工作流返回 400

*校验失败*  |  `API`  |  7.6

- **现象**：POST /prompt 返回 prompt_outputs_failed_validation。
- **处理**：看响应体里的 node_errors：required_input_missing 是输入名写错（如 CFGGuider 用 positive/negative 而非 conditioning）；value_not_in_list 是枚举值非法（如 SeedVR2 的 device 必须是 cuda:0）。

### ERROR 7 · 更新后节点突然失效

*ComfyUI 自动更新*  |  `UPDATE`  |  7.7

- **现象**：重启 ComfyUI 后某些节点消失或导入失败。
- **处理**：Windows portable 会在启动时自动更新版本（实测 0.28.0 → 0.38.2），部分节点包需要重新安装。
- **要点**：排障时先看启动日志里的 ComfyUI 版本号。

### ERROR 8 · 出图被拉伸或两侧留黑边

*自研出图工具*  |  `TOOLING`  |  7.8

- **现象**：对比图里图片比例被改，或左右出现黑边。
- **根因**：把源图裁成目标比例时，如果源图比目标更窄，错误地去「加宽」，负数裁切会被图像库填成黑边；或者把不同宽高比的图直接拉伸进同一槽位。
- **处理**：裁切只允许裁剪、不允许加宽；不同宽高比的图放进同一槽位时按等比缩放并居中留白，绝不拉伸。

## 附录 A · 参数速查表

*APPENDIX A · QUICK REFERENCE*

| 参数 | 所属 | 取值 | 说明 |
|---|---|---|---|
| upscaling_mode | DLSS5 | 1x(DLAA) / 1.5x / 2x / 3x | 1x 只增强不放大，2x 常规 |
| nr_style | DLSS5 | Natural / Cinematic | Natural 贴近原图 |
| dlss_model_preset | DLSS5 | J / K / L / M | M 纹理重建最强 |
| local_structure_strength | DLSS5 | 0-2，默认 1.5 | AI 素材 1.2-1.6 |
| verify_neural_rendering | DLSS5 | 保持开启 | 没有签名执行就报错，不降级 |
| cfg | FLUX2 | 1 | Klein 蒸馏模型固定值 |
| steps | FLUX2 | 4 | 加步数会过曝 |
| sampler / scheduler | FLUX2 | euler / Flux2Scheduler | 尺寸要按实际分辨率填 |
| resolution | SeedVR2 | 目标短边像素 | 1536×672 想 2x 填 1344 |
| color_correction | SeedVR2 | wavelet / adain / lab / hsv / none | wavelet 细节最好 |

## 附录 B · 资源与清单

*APPENDIX B · RESOURCES*

| 资源 | 用途 | 获取 |
|---|---|---|
| ComfyUI-DLSS5-Enhancer | DLSS5 节点（社区封装，MIT） | ComfyUI Manager 搜索 DLSS5 |
| dlss5-visual-enhancer v3.0 | DLSS5 原生运行时（编译期下载） | install_runtime.py 自动拉取 |
| 1x-ReFocus-V3.pth | 1x 细节重建模型（67MB） | HuggingFace: notkenski/upscalers |
| 4x-UltraSharp.pth | 通用 4x 放大 | ESRGAN 社区 |
| flux-2-klein-9b/4b-fp8 | FLUX2 主模型 | ComfyUI 官方发布 |
| seedvr2_ema_3b_fp8 | SeedVR2 DiT（3.4GB） | 首次运行自动下载 |

> **注：** 本手册由真实管线产物反推写成：手册中出现的每一张图、每一个数字都对应一次实际推理，而非示意稿。复现时若结果有出入，优先检查 PyTorch 的 CUDA 版本与模型所在存储介质——这两项是全部差异的主要来源。
