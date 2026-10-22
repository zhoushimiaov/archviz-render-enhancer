#!/usr/bin/env python3
"""小红书海报式图文卡片生成器（1080×1440，3:4 竖版）。

版式语言（参照海报样张）：
  · 整幅大图铺满 + 细网格线叠加
  · 顶部：Montserrat Light 拉丁字，字距拉开
  · 中部：黑色高亮条带 + 思源黑体白字标题，左侧一枚黄色小十字
  · 下方：Montserrat Light 的 [ 方括号副标 ]
  · 底部：Montserrat Light 部署名小字
  · 可选：珊瑚红手绘箭头

字体：思源黑体（SOURCEHANSANSSC）+ Montserrat。
用法见 --help。
"""
import argparse
import math
import os
import random

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1440
SYS = r"C:\Windows\Fonts"
USR = r"C:\Users\Administrator\AppData\Local\Microsoft\Windows\Fonts"

FONT_DIRS = [USR, SYS]
MONO = os.path.join(SYS, "consola.ttf")


def find_font(prefix, weight, exts=(".OTF", ".otf", ".TTF", ".ttf")):
    """在常见字体目录里找字体，找不到返回 None（调用方回退到系统字）"""
    for d in FONT_DIRS:
        for e in exts:
            p = os.path.join(d, f"{prefix}-{weight}{e}")
            if os.path.exists(p):
                return p
    return None

RED = (238, 62, 51)
YELLOW = (255, 214, 0)
WHITE = (255, 255, 255)


def shan(weight, size):
    """思源黑体（缺失时回退微软雅黑）"""
    p = find_font("SOURCEHANSANSSC", weight)
    if p is None:
        p = os.path.join(SYS, "msyh.ttc")
        return ImageFont.truetype(p, size)
    return ImageFont.truetype(p, size)


def mon(weight, size):
    """Montserrat（缺失时回退 Segoe UI Light）"""
    p = find_font("Montserrat", weight)
    if p is None:
        p = os.path.join(SYS, "segoeuil.ttf")
        return ImageFont.truetype(p, size)
    return ImageFont.truetype(p, size)


def mono(size):
    return ImageFont.truetype(MONO, size)


def paste_fill(img, path, box, focus=(0.5, 0.45)):
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    im = Image.open(path).convert("RGB")
    s = max(bw / im.width, bh / im.height)
    im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    l = int((im.width - bw) * focus[0])
    t = int((im.height - bh) * focus[1])
    img.paste(im.crop((l, t, l + bw, t + bh)), (x0, y0))


def grid_overlay(img, step=90, alpha=34):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for x in range(0, W, step):
        d.line([(x, 0), (x, H)], fill=(255, 255, 255, alpha), width=1)
    for y in range(0, H, step):
        d.line([(0, y), (W, y)], fill=(255, 255, 255, alpha), width=1)
    img.paste(ov, (0, 0), ov)


def scrim(img, top, bottom, strength=150):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    h = max(1, bottom - top)
    for y in range(top, bottom):
        a = int(strength * (1 - (y - top) / h) ** 1.4)
        d.line([(0, y), (W, y)], fill=(0, 0, 0, a))
    img.paste(ov, (0, 0), ov)


def spaced(draw, xy, s, font, fill, gap=12):
    x, y = xy
    for ch in s:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + gap
    return x


def black_band(draw, x, y, s, font, padx=30, pady=14):
    tw = draw.textlength(s, font=font)
    h = font.size + pady * 2
    draw.rectangle((x, y, x + tw + padx * 2, y + h), fill=(12, 12, 14))
    draw.text((x + padx, y + pady - 6), s, font=font, fill=WHITE)
    return y + h


def yellow_mark(draw, x, y, size=24, color=YELLOW, w=5):
    draw.line([(x, y - size), (x, y + size)], fill=color, width=w)
    draw.line([(x - size, y), (x + size, y)], fill=color, width=w)


def hand_arrow(draw, p0, p1, color=RED, width=9, seed=1, head=44, bow=24):
    rnd = random.Random(seed)
    x0, y0 = p0
    x1, y1 = p1
    n = 4
    pts = [(x0, y0)]
    for i in range(1, n):
        t = i / n
        pts.append((x0 + (x1 - x0) * t + rnd.uniform(-bow, bow),
                    y0 + (y1 - y0) * t + rnd.uniform(-bow, bow)))
    pts.append((x1, y1))
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=color, width=width, joint="curve")
    ang = math.atan2(y1 - pts[-2][1], x1 - pts[-2][0])
    for s in (2.5, -2.5):
        draw.line([(x1, y1), (x1 + head * math.cos(ang + s), y1 + head * math.sin(ang + s))],
                  fill=color, width=width)


def mix_text(draw, xy, s, size, color, cjk="Regular"):
    """中英混排：中文用思源黑体，拉丁/数字用 Montserrat"""
    x, y = xy
    for ch in s:
        f = shan(cjk, size) if ord(ch) > 0x2E80 else mon("Light", size)
        draw.text((x, y), ch, font=f, fill=color)
        x += draw.textlength(ch, font=f)
    return x


def fit_slot(src, w, h, bg=(14, 14, 16)):
    """把图放进 w×h 的槽位：绝不拉伸变形。
    源图更宽 -> 裁左右；源图更高 -> 按宽缩放、上下留白。"""
    sw, sh = src.size
    a_s, a_t = sw / sh, w / h
    if a_s > a_t + 1e-6:                      # 相对更宽：裁左右
        nw = int(round(sh * a_t))
        left = (sw - nw) // 2
        src = src.crop((left, 0, left + nw, sh))
        return src.resize((w, h), Image.LANCZOS)
    nh = int(round(w / a_s))                  # 相对更高：按宽缩放，上下留白
    im = src.resize((w, max(1, nh)), Image.LANCZOS)
    if im.height >= h:
        return im.crop((0, 0, w, h))
    canvas = Image.new("RGB", (w, h), bg)
    canvas.paste(im, (0, (h - im.height) // 2))
    return canvas


def measure_mixed(draw, text, size, cjk="Light"):
    """中英混排文本的像素宽度：中文用思源黑体，拉丁/数字用 Montserrat。"""
    w = 0.0
    for ch in text:
        f = shan(cjk, size) if ord(ch) > 0x2E80 else mon("Light", size)
        w += draw.textlength(ch, font=f)
    return w


def poster(args):
    img = Image.new("RGB", (W, H), (20, 20, 22))
    if args.hero and os.path.exists(args.hero):
        paste_fill(img, args.hero, (0, 0, W, H), focus=(args.fx, args.fy))
    grid_overlay(img, args.grid_step, min(args.grid_alpha, 12))   # 海报网格压淡，不挡画面
    d = ImageDraw.Draw(img)
    M = 70

    # 顶部拉丁字：黑底胶囊（不靠渐变压图）
    kf = mon("Medium", 50)
    ktxt = args.top.upper()
    kw = sum(d.textlength(c, font=kf) for c in ktxt) + 15 * (len(ktxt) - 1)
    d.rounded_rectangle((M, 76, M + kw + 56, 76 + 74), radius=5, fill=(14, 14, 16))
    spaced(d, (M + 28, 88), ktxt, kf, WHITE, 15)

    y = args.band_y
    yellow_mark(d, M + 6, y + 34, 22)
    black_band(d, M + 44, y, args.band, shan(args.band_weight, args.band_size))
    y += args.band_size + 28 + 44

    if args.sub:
        f = mon("Light", args.sub_size)
        tw = measure_mixed(d, args.sub, args.sub_size, cjk="Light")
        br_w = d.textlength("[", font=f)
        pad = int(f.size * 0.45)
        bx0 = M + 30
        bx1 = bx0 + pad + br_w + int(tw) + br_w + pad
        d.rectangle((bx0, y - 10, bx1, y + f.size + 12), fill=(14, 14, 16))
        d.text((bx0 + pad, y), "[", font=f, fill=WHITE)
        x = mix_text(d, (bx0 + pad + br_w + 6, y), args.sub, args.sub_size, WHITE, cjk="Light")
        d.text((x + 6, y), "]", font=f, fill=WHITE)

    if args.extra and args.show_bottom:
        mix_text(d, (M + 44, H - 176), args.extra, 28, (246, 246, 248))
    if args.credit and args.show_bottom:
        mix_text(d, (M + 44, H - 112), args.credit, 25, (238, 238, 240))

    if args.arrow:
        hand_arrow(d, (W - M - 40, args.arrow_y), (args.arrow_x, args.arrow_y - 160), seed=args.seed)
    img.save(args.out)
    print("saved:", args.out)


def compare_poster(args):
    img = Image.new("RGB", (W, H), (16, 16, 18))
    d = ImageDraw.Draw(img)
    for x in range(0, W, args.grid_step):
        d.line([(x, 0), (x, H)], fill=(40, 40, 44), width=1)
    for y in range(0, H, args.grid_step):
        d.line([(0, y), (W, y)], fill=(40, 40, 44), width=1)
    spaced(d, (70, 74), args.top.upper(), mon("Medium", 42), (226, 226, 230), 13)
    black_band(d, 112, 132, args.band, shan("Bold", 56))
    f = mon("Light", 38)
    d.text((112, 232), "[", font=f, fill=(226, 226, 230))
    x = mix_text(d, (112 + f.size * 0.5, 232), args.sub, 38, (226, 226, 230), cjk="Light")
    d.text((x + f.size * 0.1, 232), "]", font=f, fill=(226, 226, 230))

    top = 300
    cell = (W - 40) // 2
    for i, spec in enumerate(args.image):
        label, path = spec.split("=", 1)
        cx = 20 + (i % 2) * cell
        cy = top + (i // 2) * cell
        im = Image.open(path).convert("RGB")
        side = min(im.width, im.height)
        l = (im.width - side) // 2
        t = (im.height - side) // 2
        im = im.crop((l, t, l + side, t + side)).resize((cell, cell), Image.LANCZOS)
        img.paste(im, (cx, cy))
        d = ImageDraw.Draw(img)
        d.rectangle((cx, cy + cell - 54, cx + cell, cy + cell), fill=(10, 10, 12))
        d.text((cx + 16, cy + cell - 46), label, font=shan("Medium", 30), fill=WHITE)

    mix_text(d, (20, H - 92), args.credit, 25, (230, 230, 232))
    if args.arrow:
        hand_arrow(d, (W - 60, top + cell // 2 + 30), (20 + cell + cell // 2, top + cell // 2 - 40),
                   seed=args.seed)
    img.save(args.out)
    print("saved:", args.out)


def steps_poster(args):
    img = Image.new("RGB", (W, H), (20, 20, 22))
    if args.hero and os.path.exists(args.hero):
        paste_fill(img, args.hero, (0, 0, W, H), focus=(args.fx, args.fy))
    grid_overlay(img, 90, 30)
    scrim(img, 340, H, 200)
    scrim(img, H - 260, H, 150)
    d = ImageDraw.Draw(img)
    spaced(d, (70, 90), args.top.upper(), mon("Medium", 46), WHITE, 13)
    black_band(d, 112, 152, args.band, shan("Bold", 54))
    mix_text(d, (112, 246), "[ " + args.sub + " ]", 36, (236, 236, 238), cjk="Light")

    y = 560
    for item in args.item:
        no, title, cmd = (item.split("|") + ["", "", ""])[:3]
        d.text((70, y), no, font=mon("Medium", 25), fill=YELLOW)
        d.text((170, y - 8), title, font=shan("Bold", 36), fill=WHITE)
        d.rectangle((70, y + 50, W - 70, y + 114), fill=(10, 10, 12))
        d.text((92, y + 68), cmd, font=mono(24), fill=(150, 225, 160))
        y += 148
    mix_text(d, (70, H - 100), args.credit, 25, (236, 236, 238))
    if args.arrow:
        hand_arrow(d, (W - 130, H - 190), (W - 430, H - 300), seed=args.seed)
    img.save(args.out)
    print("saved:", args.out)


def stack_poster(args):
    """纵向四图对比：标题区 + 四张图从上到下排列
    --light 白底；--long 长图通栏（整幅不裁切）；默认 3:4（整幅不裁切，居中）"""
    if args.light:
        bg, grid, ink, dim = (255, 255, 255), (234, 234, 238), (26, 26, 30), (124, 124, 132)
    else:
        bg, grid, ink, dim = (14, 14, 16), (38, 38, 43), (222, 222, 226), (190, 190, 198)
    imgs = args.image
    n = len(imgs)
    with Image.open(imgs[0].split("=", 1)[1]) as probe:
        ar = probe.width / probe.height

    if args.long:                       # 长图：通栏、整幅不裁
        img_h = int(W / ar)
        ch = 214 + n * img_h + (n - 1) * 10 + 66
    else:                               # 3:4：整幅不裁、居中
        ch = H
    img = Image.new("RGB", (W, ch), bg)
    d = ImageDraw.Draw(img)
    for x in range(0, W, args.grid_step):
        d.line([(x, 0), (x, H if not args.long else ch)], fill=grid, width=1)
    for y in range(0, ch, args.grid_step):
        d.line([(0, y), (W, y)], fill=grid, width=1)

    ky = 44 if (args.full_width or args.long) else 58
    spaced(d, (70, ky), args.top.upper(), mon("Medium", 32 if (args.full_width or args.long) else 36), dim, 13)
    black_band(d, 112, ky + 44, args.band, shan("Bold", 40 if (args.full_width or args.long) else 48))
    if args.sub:
        f = mon("Light", 30)
        d.text((112, ky + 122), "[", font=f, fill=ink)
        x = mix_text(d, (112 + f.size * 0.5, ky + 122), args.sub, 30, ink, cjk="Light")
        d.text((x + f.size * 0.1, ky + 122), "]", font=f, fill=ink)

    gap = 10
    if args.long:
        top, bottom = 214, ch - 66
        h = int((bottom - top - gap * (n - 1)) / n)
        w, x0 = W, 0
    else:
        top, bottom = 228, ch - 46
        h = int((bottom - top - gap * (n - 1)) / n)
        w = int(h * ar)
        if w > W - 60:                         # 太宽就按宽定，再回算高，保证不拉伸
            w = W - 60
            h = int(w / ar)
        x0 = (W - w) // 2
    for i, spec in enumerate(imgs):
        label, path = spec.split("=", 1)
        y = top + i * (h + gap)
        im = fit_slot(Image.open(path).convert("RGB"), w, h, bg)
        img.paste(im, (x0, y))
        d = ImageDraw.Draw(img)
        lf = shan("Medium", 26)
        lw = d.textlength(label, font=lf)
        d.rectangle((x0, y + h - 46, x0 + lw + 32, y + h), fill=(10, 10, 12))
        d.text((x0 + 16, y + h - 38), label, font=lf, fill=WHITE)
    if args.credit and args.show_bottom:
        mix_text(d, (70, ch - 40 if args.full_width else ch - 56), args.credit, 24, dim)
    img.save(args.out)
    print("saved:", args.out, img.size)


def quad_poster(args):
    """四格对比：标题区 + 2×2 网格（整幅不裁切）"""
    imgs = args.image
    n = len(imgs)
    cols = 2
    rows = (n + cols - 1) // cols
    with Image.open(imgs[0].split("=", 1)[1]) as probe:
        ar = probe.width / probe.height
    cell_w = (W - 24) // cols
    cell_h = int(cell_w / ar)
    grid_h = rows * cell_h + (rows - 1) * 12
    ch = 196 + grid_h + 24
    img = Image.new("RGB", (W, ch), (14, 14, 16))
    d = ImageDraw.Draw(img)
    for x in range(0, W, args.grid_step):
        d.line([(x, 0), (x, ch)], fill=(38, 38, 43), width=1)
    for y in range(0, ch, args.grid_step):
        d.line([(0, y), (W, y)], fill=(38, 38, 43), width=1)
    spaced(d, (70, 52), args.top.upper(), mon("Medium", 40), (222, 222, 226), 13)
    black_band(d, 112, 106, args.band, shan("Bold", 48))
    for i, spec in enumerate(imgs):
        label, path = spec.split("=", 1)
        cx = 12 + (i % cols) * (cell_w + 12)
        cy = 196 + (i // cols) * (cell_h + 12)
        im = fit_slot(Image.open(path).convert("RGB"), cell_w, cell_h, (14, 14, 16))
        img.paste(im, (cx, cy))
        d = ImageDraw.Draw(img)
        lf = shan("Medium", 26)
        lw = d.textlength(label, font=lf)
        d.rectangle((cx, cy + cell_h - 46, cx + lw + 32, cy + cell_h), fill=(10, 10, 12))
        d.text((cx + 16, cy + cell_h - 38), label, font=lf, fill=WHITE)
    img.save(args.out)
    print("saved:", args.out, img.size)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", default="poster", choices=["poster", "compare", "steps", "stack", "quad"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--hero")
    ap.add_argument("--top", default="COMFYUI")
    ap.add_argument("--band", required=True)
    ap.add_argument("--band-size", type=int, default=66)
    ap.add_argument("--band-weight", default="Bold")
    ap.add_argument("--band-y", type=int, default=520)
    ap.add_argument("--sub", default="")
    ap.add_argument("--sub-size", type=int, default=52)
    ap.add_argument("--credit", default="")
    ap.add_argument("--extra", default="")
    ap.add_argument("--image", action="append", default=[])
    ap.add_argument("--item", action="append", default=[])
    ap.add_argument("--fx", type=float, default=0.5)
    ap.add_argument("--fy", type=float, default=0.45)
    ap.add_argument("--grid-step", type=int, default=30)
    ap.add_argument("--grid-alpha", type=int, default=34)
    ap.add_argument("--scrim", type=float, default=0.35)
    ap.add_argument("--scrim-strength", type=int, default=150)
    ap.add_argument("--arrow", action="store_true")
    ap.add_argument("--full-width", action="store_true", help="纵向四图左右撑满")
    ap.add_argument("--band-focus", type=float, default=0.5, help="通栏切片的取景位置 0=顶 1=底")
    ap.add_argument("--light", action="store_true", help="白底版式")
    ap.add_argument("--long", action="store_true", help="长图通栏版（整幅不裁切）")
    ap.add_argument("--show-bottom", action="store_true", help="显示底部说明文字（默认关闭）")
    ap.add_argument("--arrow-x", type=int, default=700)
    ap.add_argument("--arrow-y", type=int, default=900)
    ap.add_argument("--seed", type=int, default=3)
    args = ap.parse_args()
    d = os.path.dirname(os.path.abspath(args.out))
    if d:
        os.makedirs(d, exist_ok=True)
    {"poster": poster, "compare": compare_poster, "steps": steps_poster, "stack": stack_poster, "quad": quad_poster}[args.kind](args)


if __name__ == "__main__":
    main()
