# 常见故障与处理

## 1. 加载 fp8 模型时进程瞬间消失（Windows "page error"）

**现象**：ComfyUI 进程无 Python 堆栈直接退出，日志最后一行可能是
`Using MixedPrecisionOps for text encoder` 或 `comfy/ops.py _quantized_apply`。

**根因**：ComfyUI 0.28+ 的 `comfy_kitchen` 要求 CUDA ≥ 13.0；cu126 环境下
fp8 权重被降级到 eager 分发路径，在部分机器上直接触发访问违例。

**处理**：把 ComfyUI 嵌入式 Python 的 torch 三件套升到 cu130（见 environment.md）。
验证方式：启动日志出现 `Found comfy_kitchen backend cuda: ... 'disabled': False`。

**回滚**：重装 `+cu126` 版本即可，模型文件无需重下。

## 2. 浏览器一直显示 "Reconnecting"

服务器重启过或进程退出后，页面里的 websocket 断开且不会自动重连。

- 先确认服务在跑：`curl http://127.0.0.1:8188/system_stats`
- 在的话按 **F5** 刷新页面
- 不在就看启动日志尾部有没有异常；ComfyUI portable 有时会在启动时**自动更新版本**
  （日志里 ComfyUI 版本号会变），更新后部分自定义节点需要重新安装
- Windows 上后台启动的 ComfyUI 建议用 `Start-Process` 脱离会话，否则会话结束进程会被回收

## 3. 报"缺失模型 xxx.pth"

工作流引用了本地没有的模型文件。常见于从别的机器导入的工作流。

- 用 ComfyUI 右侧面板的"缺失模型"条目里的下载链接，或手工下载后放进
  `ComfyUI/models/<对应目录>/`
- 放完**不用重启**，`/object_info` 会立刻列出新文件
- 常用缺失件与来源：
  - `1x-ReFocus-V3.pth` → HuggingFace `notkenski/upscalers`（约 67MB）→ `models/upscale_models/`
  - `4x-UltraSharp.pth` → ESRGAN 社区 → `models/upscale_models/`
  - `seedvr2_ema_3b_fp8_e4m3fn.safetensors` → **无需手工下载**，SeedVR2 节点首次运行自动拉取

## 4. 远端调用报 missing node type

目标机（worker）缺少主控机工作流用到的自定义节点。

```bash
# 查两边的节点差异
python scripts/check_env.py --host <远端IP> --port 8188
```

在 worker 上装齐同样的节点包，并把工作流里用到的模型也放过去（或在 worker 上
用同样的 `extra_model_paths.yaml` 挂载）。

## 5. 模型加载慢得离谱（十几分钟起）

几乎都是**存储问题**而不是算力问题：模型在机械盘上，safetensors 的 mmap 小块
随机读被拖到 1MB/s 级别。

- 把热模型移到 NVMe，机械盘只放冷模型 + `extra_model_paths.yaml` 挂载
- 参考同机实测：NVMe 随机读 552MB/s vs 机械盘 0.98MB/s，差 560 倍
- 首次运行后模型会留在内存/显存里，后续同模型出图是秒级

## 6. DLSS5 节点报 "The native DLSS worker did not exit within 60 seconds"

节点包在收尾时等不到原生 worker 退出，强杀并抛出该异常。

- 只影响那一次任务，重跑即可
- 频繁出现说明 worker 会话状态有问题：可关掉并重启 ComfyUI
- 该节点默认开启 `verify_neural_rendering`，如果 ReShade 日志里没有签名过的
  feature-18 执行会**直接报错而不是悄悄降级**——这是设计如此，别去关它

## 7. SeedVR2 首次运行卡住 / 报下载失败

SeedVR2 权重约 3–4GB，首次运行自动下载。

- 确认 `models/diffusion_models/` 所在盘剩余空间足够
- 下载失败时手动放置：`seedvr2_ema_3b_fp8_e4m3fn.safetensors` + `ema_vae_fp16.safetensors`
- 显存紧张时把 `SeedVR2LoadDiTModel` 的 model 换成 `seedvr2_ema_3b-Q4_K_M.gguf`

## 8. 提交工作流返回 400

先看响应体里的 `node_errors`，最常见两类：

- `required_input_missing`：节点输入名写错了（各版本输入名会变，例如
  `CFGGuider` 用 `positive`/`negative`，不是 `conditioning`）
- `value_not_in_list`：枚举值不合法（例如 SeedVR2 的 `device` 必须是 `cuda:0` 而不是 `cuda`）

## 9. 远端 ComfyUI 没有鉴权

`--listen 0.0.0.0` 等于把任务提交与文件读取开放给整个局域网。

- 仅限内网使用，**不要做公网端口映射**
- 需要收紧时用 Windows 防火墙规则限定来源 IP，例如只允许你自己那台的局域网地址
- 产物也可被同网段任意设备通过 `/view` 取走，注意客户图不要放公网可达的机器
