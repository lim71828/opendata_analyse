# -*- coding: utf-8 -*-
"""
第 2 步：探索性数据分析（EDA）
================================
目标：从多个角度刻画数据形态——
  1) 单变量分布（直方图/箱线图）
  2) 目标变量与各特征的关联（购买率对比）
  3) 变量间相关性（热力图）
  4) 类别不平衡与有偏分布的处理建议

要点：本脚本只读不写，不对原始数据集做任何修改。
"""
import os
import sys

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

# 中文字体支持（Windows）——先设 seaborn 样式再设字体，避免被 set_style 覆盖
sns.set_style("whitegrid")
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans SC", "sans-serif"]
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.unicode_minus"] = False

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_utils import check_overlap

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = r"C:\Users\18887\Downloads\social_ecommerce_data.csv"
FIG = os.path.join(BASE, "output", "figures")
os.makedirs(FIG, exist_ok=True)

df = pd.read_csv(RAW)
print(f"数据规模: {df.shape}")

# ---------------- 1. 单变量分布 ----------------
def save_fig(fig, name):
    # 保存前先检测文本重叠
    check_overlap(fig, name)
    path = os.path.join(FIG, name)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  已保存: {name}")

# 年龄分布
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
sns.histplot(df["age"], bins=24, kde=True, color="#4C72B0", ax=axes[0])
axes[0].set_title("用户年龄分布")
axes[0].set_xlabel("年龄")
# 按购买与否分组的年龄分布
sns.kdeplot(df.loc[df.label == 0, "age"], label="未购买", fill=True, color="#C44E52", ax=axes[1])
sns.kdeplot(df.loc[df.label == 1, "age"], label="已购买", fill=True, color="#55A868", ax=axes[1])
axes[1].set_title("年龄分布：按购买标签")
axes[1].set_xlabel("年龄")
save_fig(fig, "01_年龄分布.png")

# 价格分布（右偏明显 -> log 处理前后对比）
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
sns.histplot(df["price"], bins=60, color="#4C72B0", ax=axes[0])
axes[0].set_title("商品价格分布（原始，右偏）")
sns.histplot(np.log1p(df["price"]), bins=60, color="#DD8452", ax=axes[1])
axes[1].set_title("商品价格分布（log1p 变换）")
save_fig(fig, "02_价格分布与log变换.png")

# 累计消费分布
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
sns.histplot(np.log1p(df["total_spend"]), bins=60, color="#4C72B0", ax=axes[0])
axes[0].set_title("累计消费 log1p 分布")
sns.boxplot(data=df, x="label", y=np.log1p(df["total_spend"]), ax=axes[1])
axes[1].set_title("累计消费(log) vs 购买标签")
axes[1].set_xticklabels(["未购买", "已购买"])
save_fig(fig, "03_累计消费分布.png")

# 互动指标分布（点赞/评论/分享/收藏）右偏
fig, axes = plt.subplots(2, 2, figsize=(15, 10))
for ax, col, cn in zip(axes.ravel(),
                        ["like_num", "comment_num", "share_num", "collect_num"],
                        ["点赞数", "评论数", "分享数", "收藏数"]):
    vals = np.log1p(df[col])
    sns.histplot(vals, bins=50, kde=True, ax=ax)
    ax.set_title(f"{cn}({col}) log1p 分布")
    ax.set_xlabel("log1p值")
    # 显式限定坐标轴范围与刻度：左界 0、右界按数据最大值取整，
    # 刻度完全手动指定——避免 locator 生成越界刻度画到坐标轴外侧压到相邻子图
    ax.set_xlim(0, np.ceil(vals.max()) + 0.2)
    ax.set_xticks(np.arange(0, int(np.ceil(vals.max())) + 1, 2))
# 用 tight_layout 的间距参数加大子图间留白（注意：不能与 subplots_adjust 混用）
fig.tight_layout(pad=2.0, w_pad=2.5, h_pad=2.5)
save_fig(fig, "04_互动指标log分布.png")

# ---------------- 2. 目标变量与特征关联 ----------------
def purchase_rate_by(df, col, title, labels=None, top=None, ordered=None, colors=None):
    """计算各取值下的购买率（横向条形图）。
    注意：使用 matplotlib 原生 barh 而非 seaborn barplot——
    避免将数值列"购买率%"传入 x 后被当作连续尺度，导致刻度文字密集重叠。
    colors: dict，按重命名后的类别名 -> 颜色，用于对特定取值指定条形颜色。"""
    grp = df.groupby(col, observed=True)["label"].agg(["mean", "count"])
    grp.columns = ["购买率", "样本数"]
    grp["购买率%"] = (grp["购买率"] * 100).round(1)
    grp = grp.sort_values("购买率%", ascending=False)
    if top:
        grp = grp.head(top)
    if ordered is not None:
        grp = grp.reindex([c for c in ordered if c in grp.index]).dropna()
    if labels:
        grp = grp.rename(index=labels)

    cats = grp.index.astype(str).tolist()
    rates = grp["购买率%"].values
    ypos = np.arange(len(cats))[::-1]  # 购买率最高者置顶

    if colors is not None:
        bar_colors = [colors.get(c, "#7F8C9E") for c in cats]
    else:
        bar_colors = plt.cm.magma(np.linspace(0.2, 0.85, len(cats)))

    fig, ax = plt.subplots(figsize=(10, max(4, 0.6 * len(cats) + 2)))
    ax.barh(ypos, rates, color=bar_colors, height=0.6)
    ax.set_yticks(ypos)
    ax.set_yticklabels(cats)
    # 文本 y 必须与条形 ypos 一致，否则百分比数与所属条形上下错位
    for i, (rate, n) in enumerate(zip(rates, grp["样本数"])):
        ax.text(rate + 0.8, ypos[i], f"{rate:.1f}% (n={int(n):,})", va="center", fontsize=9)
    ax.set_xlim(0, rates.max() + 22)
    ax.set_xlabel("购买率%")
    ax.set_title(f"{title} —— 各取值购买率")
    return grp

# 类目购买率
cat_grp = purchase_rate_by(df, "category", "商品类目")
save_fig(plt.gcf(), "05_类目购买率.png")
cat_grp.round(2).to_csv(os.path.join(BASE, "output", "overview", "类目购买率.csv"))

# 用户等级购买率
lv_grp = purchase_rate_by(df, "user_level", "用户等级")
save_fig(plt.gcf(), "06_用户等级购买率.png")

# 性别购买率
gd_grp = purchase_rate_by(df, "gender", "性别", labels={0: "女", 1: "男"})
save_fig(plt.gcf(), "07_性别购买率.png")

# 是否有视频
vd_grp = purchase_rate_by(df, "has_video", "是否含视频", labels={0: "无视频", 1: "有视频"})
save_fig(plt.gcf(), "08_视频购买率.png")

# 是否关注作者
fa_grp = purchase_rate_by(df, "is_follow_author", "是否关注作者",
                          labels={0: "未关注", 1: "已关注"},
                          colors={"未关注": "#6B7F8F", "已关注": "#A9D2E4"})
save_fig(plt.gcf(), "09_关注作者购买率.png")

# 加购 / 领券 / 用券 与购买率（"是"即已发生状态用浅色，与 09 保持一致）
for col, cn in [("add2cart", "是否加购"), ("coupon_received", "是否领券"), ("coupon_used", "是否用券")]:
    g = purchase_rate_by(df, col, cn,
                         labels={0: "否", 1: "是"},
                         colors={"否": "#6B7F8F", "是": "#A9D2E4"})
    save_fig(plt.gcf(), f"10_{cn}购买率.png")

# 连续特征按分箱看购买率（价格）
fig, axes = plt.subplots(1, 3, figsize=(18, 5))
# 价格分箱
df["price_bin"] = pd.qcut(df["price"], 8, duplicates="drop")
pr = df.groupby("price_bin", observed=True)["label"].mean() * 100
pr.plot(kind="bar", ax=axes[0], color="#DD8452")
axes[0].set_title("价格分箱 -> 购买率")
axes[0].set_ylabel("购买率%")
# 最近点击间隔分箱
df["gap_bin"] = pd.qcut(df["last_click_gap"], 8, duplicates="drop")
gap = df.groupby("gap_bin", observed=True)["label"].mean() * 100
gap.plot(kind="bar", ax=axes[1], color="#4C72B0")
axes[1].set_title("距上次点击间隔 -> 购买率")
axes[1].set_ylabel("购买率%")
# 浏览量分箱
df["pv_bin"] = pd.qcut(df["pv_count"], 8, duplicates="drop")
pv = df.groupby("pv_bin", observed=True)["label"].mean() * 100
pv.plot(kind="bar", ax=axes[2], color="#55A868")
axes[2].set_title("近7天浏览 -> 购买率")
axes[2].set_ylabel("购买率%")
fig.tight_layout()
save_fig(fig, "11_连续特征分箱购买率.png")

# ---------------- 3. 相关性热力图 ----------------
num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
# 与目标的相关性（点二列相关 / Pearson）
corr = df[num_cols].corr(method="pearson")["label"].drop("label").sort_values()
print("\n【各数值特征与 label 的 Pearson 相关系数】(升序)")
print(corr.round(4).to_string())

fig, ax = plt.subplots(figsize=(16, 13))
mask = np.triu(np.ones_like(df[num_cols].corr(), dtype=bool), k=1)
sns.heatmap(df[num_cols].corr(), mask=mask, cmap="RdBu_r", center=0,
            annot=False, ax=ax, square=True, linewidths=0.3)
ax.set_title("数值特征相关性热力图")
save_fig(fig, "12_相关性热力图.png")

# 与 label 相关性的条形图
fig, ax = plt.subplots(figsize=(10, 10))
corr.plot(kind="barh", color=["#C44E52" if v < 0 else "#55A868" for v in corr.values], ax=ax)
ax.set_title("特征与目标(label)的相关系数")
ax.set_xlabel("Pearson 相关系数")
save_fig(fig, "13_特征与目标相关性.png")

corr.round(4).to_csv(os.path.join(BASE, "output", "overview", "特征与目标相关性.csv"))

# ---------------- 4. 类别不平衡观察 ----------------
pos = (df.label == 1).mean()
print(f"\n正样本占比: {pos:.2%}  (正负比 1 : {1 / pos - 1:.2f})")
print("说明：原描述称正负比约 1:4，实测接近均衡(约 1:1.22)，建模时应以实际分布为准。")

# ---------------- 5. 衍生特征质量核查 ----------------
print("\n【衍生特征一致性核查】")
print(f"  interaction_rate 与 (like+comment+share+collect)/互动 的关系待验证")
# 检查 purchase_intent 与 add2cart/coupon_used 的关联
print("\n【purchase_intent 分布，按行为标签】")
intent_tbl = df.groupby("add2cart")["purchase_intent"].agg(["mean", "median"])
intent_tbl.index = ["未加购", "已加购"] if set(intent_tbl.index) == {0, 1} else intent_tbl.index
print(intent_tbl.round(3).to_string())

print("\nEDA 完成，图表已输出到 output/figures/")
