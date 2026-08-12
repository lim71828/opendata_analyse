# -*- coding: utf-8 -*-
"""绘图辅助工具：文本重叠检测（用于质量控制检查图内文字是否互相遮挡）。"""
import matplotlib.pyplot as plt


def collect_texts(fig):
    """收集图中所有可见文本对象及其窗口坐标包围盒（像素）。"""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    items = []
    for ax in fig.axes:
        objs = []
        if ax.get_title():
            objs.append(("title", ax.title))
        objs.append(("xlabel", ax.xaxis.label))
        objs.append(("ylabel", ax.yaxis.label))
        for t in ax.get_xticklabels():
            objs.append(("xtick", t))
        for t in ax.get_yticklabels():
            objs.append(("ytick", t))
        for t in ax.texts:
            objs.append(("text", t))
        if ax.get_legend() is not None:
            for t in ax.get_legend().get_texts():
                objs.append(("legend", t))
        for kind, t in objs:
            if not t.get_visible():
                continue
            txt = t.get_text() or ""
            if not txt.strip():
                continue
            bb = t.get_window_extent(renderer=renderer)
            if bb.width < 1 or bb.height < 1:  # 无效/未渲染
                continue
            items.append((f"{kind}:{txt.strip()}", bb))
    return items


def check_overlap(fig, name, pad=0.0):
    """检测重叠。pad>0 时把每个包围盒外扩 pad 像素再判（更严格）。
    返回重叠对列表；空列表表示无重叠。"""
    items = collect_texts(fig)
    overlaps = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            bi, bj = items[i][1], items[j][1]
            if pad > 0:
                bi = bi.expanded(1 + pad / bi.width, 1 + pad / bi.height)
                bj = bj.expanded(1 + pad / bj.width, 1 + pad / bj.height)
            if bi.overlaps(bj):
                overlaps.append((items[i][0], items[j][0]))
    if overlaps:
        print(f"  ⚠ 检测到 {len(overlaps)} 处重叠 -> {name}")
        for a, b in overlaps[:30]:
            print(f"      「{a}」 <-> 「{b}」")
    else:
        print(f"  ✓ 无重叠 -> {name}")
    return overlaps
