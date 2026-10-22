#!/usr/bin/env python3
"""把多张图拼成对比图（等宽竖排 + 标题条）。

用法:
  python make_comparison.py --out compare.png \
      --image "A=原图.png" --image "B=DLSS5.png" --image "C=FLUX2.png" \
      --crop 480,320 --panel-width 960

--crop 传 "宽,高" 时对每张图取**中心**同尺寸区域并放大到 panel-width，
用于细节对比；不传则整图等宽缩放。
需要 Pillow: pip install pillow
"""
import argparse
import os

try:
    from PIL import Image, ImageDraw
except ImportError:
    raise SystemExit("需要 Pillow: pip install pillow")


def load(spec):
    if "=" in spec:
        label, path = spec.split("=", 1)
    else:
        label, path = os.path.basename(spec), spec
    return label, Image.open(path).convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", action="append", required=True, help="标签=路径，可重复")
    ap.add_argument("--out", required=True)
    ap.add_argument("--crop", help="宽,高 —— 中心裁剪尺寸（细节对比用）")
    ap.add_argument("--panel-width", type=int, default=960)
    ap.add_argument("--bar", type=int, default=26)
    args = ap.parse_args()

    panels = [load(s) for s in args.image]
    if len(panels) < 2:
        raise SystemExit("至少给两张图")

    if args.crop:
        cw, ch = (int(x) for x in args.crop.split(","))
        out = []
        for label, im in panels:
            l, t = (im.width - cw) // 2, (im.height - ch) // 2
            l, t = max(0, l), max(0, t)
            crop = im.crop((l, t, l + cw, t + ch))
            scale = args.panel_width / crop.width
            out.append((label, crop.resize((args.panel_width, int(crop.height * scale)), Image.LANCZOS)))
    else:
        out = []
        for label, im in panels:
            scale = args.panel_width / im.width
            out.append((label, im.resize((args.panel_width, int(im.height * scale)), Image.LANCZOS)))

    H = sum(p.height for _, p in out) + args.bar * len(out) + 4 * len(out)
    canvas = Image.new("RGB", (args.panel_width, H), (24, 24, 24))
    d = ImageDraw.Draw(canvas)
    y = 0
    for label, im in out:
        d.text((8, y + 7), label, fill=(235, 235, 235))
        canvas.paste(im, (0, y + args.bar))
        y += im.height + args.bar + 4
    canvas.save(args.out)
    print("saved:", os.path.abspath(args.out), canvas.size)


if __name__ == "__main__":
    main()
