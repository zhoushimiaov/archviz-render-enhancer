# 环境与硬件参考

> 本文件不绑定任何特定机器或地址。下面的数字来自一台参考测试机，用于说明"什么样的环境够用"；
> 你的机器不必相同，脚本通过 `--host/--port/--comfy-dir` 指向你自己的 ComfyUI 即可。

## 最低可用环境

| 项 | 要求 | 说明 |
|---|---|---|
| 显卡 | NVIDIA RTX 30/40/50 系 | DLSS 5 管线需要 RTX；RTX 20 系不支持 |
| 显存 | 8GB 起，12GB 以上更从容 | 9B 权重 + 文本编码器会轮流驻留 |
| 驱动 | 580 以上，CUDA UMD ≥ 13.0 | 低于 13.0 会让 fp8 加载走不稳定路径 |
| ComfyUI | 0.28+ | 0.38.x 已验证 |
| Python | 3.12 | Windows portable 自带嵌入式环境，无需另装 |
| 内存 | 32GB 起 | 页面文件建议 32–64GB |
| 存储 | 热模型放 NVMe/SSD | 机械盘随机读不足 1MB/s，模型加载会慢到无法忍受 |

## 参考测试机（仅供对照）

| 项 | 配置 |
|---|---|
| GPU | RTX 4080 16GB，驱动 610.88（CUDA UMD 13.3） |
| 内存 | 128GB，页面文件 8GB |
| 存储 | NVMe 1TB（ComfyUI 主安装 + 热模型）｜USB SSD｜机械 4TB×2（模型冷库） |
| ComfyUI | Windows portable，0.38.2 |
| PyTorch | 2.11.0+cu130 / torchvision 0.26.0+cu130 / torchaudio 2.11.0+cu130 |
| 第二台机 | RTX 5070 12GB，ComfyUI 0.15.1，`--listen 0.0.0.0 --port 8188` |

## 盘位实测（同一工具 winsat，可直接复现）

| 介质 | 顺序读 | 顺序写 | **随机读** |
|---|---|---|---|
| NVMe SSD | 3450 MB/s | 6440 MB/s | 552 MB/s |
| USB SSD | ~320–390 | ~300–400 | ~170–285 |
| 机械硬盘 | 32 | 143 | **0.98** |

**结论**：模型加载是 safetensors 的 mmap 小块随机读，机械盘的 0.98MB/s 会让 19GB 权重
加载从"两分钟"变成"半小时起"。热模型一律放 NVMe，冷模型用 `extra_model_paths.yaml`
挂载到慢盘，按需再读。

## 关键：PyTorch 必须 cu130+

ComfyUI 0.28+ 把 fp8 权重运算交给了 `comfy_kitchen`。该组件要求 **CUDA ≥ 13.0** 才启用
优化 CUDA 后端；cu126 会被降级到 eager 分发路径，在部分机器上加载 fp8 权重会直接触发
Windows 致命错误 `page error`（进程瞬间消失，无 Python 堆栈）。

修复（只改 ComfyUI 自带的嵌入式 Python，不影响系统 Python，**不需要重启电脑**）：

```bash
python_embeded/python.exe -m pip install \
  torch==2.11.0+cu130 torchvision==0.26.0+cu130 torchaudio==2.11.0+cu130 \
  --index-url https://download.pytorch.org/whl/cu130
```

版本要点：

- 选 **torch 2.11.0**：与多数机器原有的 2.11 一致（零行为回归），且 torchaudio 在 cu130 上
  最高只到 2.11.0——torch 2.12+ 会配不到 torchaudio
- 回滚：把 `+cu130` 换回 `+cu126` 重装即可
- 验证：启动日志出现 `Found comfy_kitchen backend cuda: ... 'disabled': False` 即为生效

## 模型摆放建议

```
<ComfyUI 安装目录>/ComfyUI/models/
├── diffusion_models/   flux-2-klein-9b-fp8, flux-2-klein-4b-fp8      (热)
├── text_encoders/      qwen_3_8b_fp8mixed, qwen_3_4b                 (热)
├── vae/                flux2-vae                                     (热)
└── upscale_models/     1x-ReFocus-V3.pth, 4x-UltraSharp\...         (热)

<慢盘>/models/                                                     ← extra_model_paths.yaml 挂载
├── text_encoders/      t5xxl×2, qwen_2.5_vl_7b（LTX-2 用）           (冷)
├── diffusion_models/   flux-2-klein-base-4b                           (冷)
└── checkpoints/        hunyuan_3d_v2.1                                (冷)
```

挂载配置示例（放在 `ComfyUI/extra_model_paths.yaml`，路径按你自己的实际位置改）：

```yaml
cold_models:
  base_path: D:\ComfyUI_models\
  checkpoints: checkpoints
  diffusion_models: diffusion_models
  text_encoders: text_encoders
  vae: vae
  loras: loras
  upscale_models: upscale_models
```

## 多机拓扑（地址由你决定）

```
用户浏览器 / 脚本
   │
   ├── 127.0.0.1:8188            ← 本机 ComfyUI（交互、DLSS5 增强、放大、SeedVR2）
   │
   └── <局域网另一台机器的IP>:8188  ← 第二台 ComfyUI（批量重绘 FLUX2 9B/4B）
          ▲ ComfyUI HTTP API：/upload/image → /prompt → /history → /view
```

- 本机用 `127.0.0.1`（或 `localhost`）；局域网用对方 IP，端口默认 8188
- 被调用方启动参数加 `--listen 0.0.0.0 --port 8188`
- 两台机的自定义节点与模型需对齐，缺节点会报 `missing node type`
- 推荐分工：**RTX 50 那台做重绘/生成，RTX 40 这台做 DLSS5 增强与放大**
- ComfyUI 的 HTTP 接口**没有鉴权**，只在内网使用，不要做公网端口映射
