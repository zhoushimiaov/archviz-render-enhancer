#!/usr/bin/env python3
"""提交 ComfyUI 工作流并等待结果（支持本机或局域网任意一台 ComfyUI）。

用法:
  # 本机
  python queue_workflow.py --host 127.0.0.1 --port 8188 \
      --workflow workflows/pipeline_a_flux2_rewrite.json \
      --input "C:/path/to/render.png" --save-dir ./out

  # 局域网另一台（把 IP 换成你自己的）
  python queue_workflow.py --host <局域网IP> --port 8188 \
      --workflow workflows/pipeline_c_hd_detail.json --input render.png

行为:
  1) 把 --input 指定的图片上传到目标 ComfyUI 的 input/ 目录;
  2) 替换工作流中所有 LoadImage 节点的文件名;
  3) POST /prompt 提交, 轮询 /history 直到完成;
  4) 把产出的图片下载到 --save-dir。
"""
import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

BOUNDARY = "----zcode" + uuid.uuid4().hex


def http_json(url, payload=None, timeout=60):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def upload_image(base, path):
    name = os.path.basename(path)
    ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
    with open(path, "rb") as f:
        data = f.read()
    body = (
        f"--{BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode("utf-8") + data + f"\r\n--{BOUNDARY}--\r\n".encode("utf-8")
    req = urllib.request.Request(
        base + "/upload/image", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.loads(r.read().decode("utf-8"))
    return out.get("name", name)


def patch_loadimage(wf, filename):
    """把所有 LoadImage 节点的 image 字段换成上传后的文件名。"""
    touched = 0
    for node in wf.values():
        if node.get("class_type") in ("LoadImage", "LoadImageOutput") and "image" in node.get("inputs", {}):
            node["inputs"]["image"] = filename
            touched += 1
    return touched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8188)
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--input", help="要处理的图片路径（会上传并自动替换 LoadImage）")
    ap.add_argument("--save-dir", default="./out", help="结果下载目录")
    ap.add_argument("--timeout", type=int, default=1800, help="等待秒数")
    ap.add_argument("--poll", type=int, default=5)
    args = ap.parse_args()

    base = f"http://{args.host}:{args.port}"
    wf = json.load(open(args.workflow, encoding="utf-8"))

    if args.input:
        if not os.path.exists(args.input):
            sys.exit(f"输入图不存在: {args.input}")
        name = upload_image(base, args.input)
        n = patch_loadimage(wf, name)
        print(f"[upload] {args.input} -> {name} (patched {n} LoadImage node(s))", flush=True)

    try:
        res = http_json(base + "/prompt", {"prompt": wf})
    except urllib.error.HTTPError as e:
        sys.exit(f"提交失败 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:800]}")
    pid = res.get("prompt_id")
    print(f"[queued] prompt_id={pid}", flush=True)

    deadline = time.time() + args.timeout
    while time.time() < deadline:
        time.sleep(args.poll)
        try:
            hist = http_json(f"{base}/history/{pid}", timeout=60)
        except Exception as e:
            print(f"[warn] 查询失败: {e}", flush=True)
            continue
        if pid not in hist:
            continue
        entry = hist[pid]
        status = entry.get("status", {})
        if status.get("status_str") == "error":
            errs = [m for m in status.get("messages", []) if m[0] == "execution_error"]
            print("[error] 节点执行失败:", flush=True)
            print(json.dumps(errs, ensure_ascii=False)[:1500], flush=True)
            sys.exit(2)
        outs = entry.get("outputs", {})
        if outs:
            os.makedirs(args.save_dir, exist_ok=True)
            saved = []
            for node_id, out in outs.items():
                for img in out.get("images", []):
                    fname = img.get("filename")
                    sub = img.get("subfolder", "")
                    url = (f"{base}/view?filename={urllib.parse.quote(fname)}"
                           f"&type={img.get('type','output')}&subfolder={urllib.parse.quote(sub)}")
                    dest = os.path.join(args.save_dir, fname)
                    with urllib.request.urlopen(url, timeout=300) as r, open(dest, "wb") as f:
                        f.write(r.read())
                    saved.append(dest)
            print(f"[done] status={status.get('status_str')} 保存 {len(saved)} 个文件:", flush=True)
            for s in saved:
                print("   ", s, flush=True)
            return
    sys.exit("[timeout] 等待超时")


if __name__ == "__main__":
    import urllib.parse
    main()
