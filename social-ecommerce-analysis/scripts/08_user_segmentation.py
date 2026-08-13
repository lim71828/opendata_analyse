# -*- coding: utf-8 -*-
"""
第 8 步：用户分层与增收运营策略
================================
目标：回答"针对每一类用户，怎么运营才能使他们花更多的钱"。

方法选择说明：
- 尝试过 KMeans 聚类，但数据显示用户层面无天然消费能力簇
  （各簇客单价 ≈ ¥110、频次 ≈ 12 次，仅购买率有差异）。
- 因此改用"业务价值分层"（RFM 式），直接按可解释、可运营的维度切分：
    M 历史消费能力：total_spend（累计消费）
    I 购买意向：purchase_intent（衍生强度）
    P 客单价杠杆：price（当前浏览商品价格，作为未来客单偏好代理）
- 目标是让每档在"花钱能力"上真实拉开差距，策略才有针对性。

口径：user_id 每用户一行 → 用户即每行；"花更多钱"= 客单价↑ 或 频次↑。
"""
import os

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans SC", "sans-serif"]
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.unicode_minus"] = False

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(BASE, "output", "processed")
FIG = os.path.join(BASE, "output", "figures")
OV = os.path.join(BASE, "output", "overview")
os.makedirs(FIG, exist_ok=True)

X = pd.read_parquet(os.path.join(PROC, "features.parquet"))
N = len(X)

# ---------------- 1. 业务价值分层 ----------------
# 1.1 历史消费能力：按累计消费 total_spend 分位切 3 档
X["价值档"] = pd.qcut(X["total_spend"], 3, labels=["低消费", "中消费", "高消费"])
# 1.2 购买意向：按 purchase_intent 中位数切 2 档
X["意向档"] = np.where(X["purchase_intent"] > X["purchase_intent"].median(), "高意向", "低意向")
# 1.3 组合成 6 类用户
X["分层"] = X["价值档"].astype(str) + "·" + X["意向档"].astype(str)

# ---------------- 2. 每层用户画像 ----------------
grp_cols = ["样本数", "占比%", "购买率%", "客单价(元)", "近30天购买次数",
            "累计消费(元)", "平均意向", "领券率%", "加购率%", "用券率%", "折扣敏感度"]
grp = X.groupby("分层", observed=True).agg(
    样本数=("label", "size"),
    购买率=("label", "mean"),
    客单价=("price", "mean"),
    近30天购买次数=("purchase_freq", "mean"),
    累计消费=("total_spend", "mean"),
    平均意向=("purchase_intent", "mean"),
    领券率=("coupon_received", "mean"),
    加购率=("add2cart", "mean"),
    用券率=("coupon_used", "mean"),
    折扣敏感度=("discount_rate", "mean"),
).reset_index()
grp["占比%"] = (grp["样本数"] / N * 100).round(2)
grp["购买率%"] = (grp["购买率"] * 100).round(2)
grp["客单价(元)"] = grp["客单价"].round(1)
grp["近30天购买次数"] = grp["近30天购买次数"].round(2)
grp["累计消费(元)"] = grp["累计消费"].round(0)
grp["平均意向"] = grp["平均意向"].round(2)
grp["领券率%"] = (grp["领券率"] * 100).round(1)
grp["加购率%"] = (grp["加购率"] * 100).round(1)
grp["用券率%"] = (grp["用券率"] * 100).round(1)
grp["折扣敏感度"] = grp["折扣敏感度"].round(3)
grp = grp.sort_values("累计消费(元)", ascending=False)
print("【用户价值分层画像】(共 6 类)")
print(grp[grp_cols].to_string(index=False))
grp[grp_cols].to_csv(os.path.join(OV, "用户价值分层画像.csv"), index=False)

# ---------------- 3. 每类用户增收策略 ----------------
base_price = X["price"].mean()
base_freq = X["purchase_freq"].mean()
base_rate = X["label"].mean()

print("\n【每类用户增收运营策略】")
strategy_lines = []
for _, r in grp.iterrows():
    seg = r["分层"]
    val_tier, intent_tier = seg.split("·")  # 从分层名解析 价值档/意向档
    price, freq, rate, spend = r["客单价(元)"], r["近30天购买次数"], r["购买率%"] / 100, r["累计消费(元)"]
    lines = [f"### {seg}",
             f"规模 {int(r['样本数']):,} 人（{r['占比%']:.1f}%）｜购买率 {r['购买率%']:.0f}%｜客单价 ¥{price:.0f}｜近30天购 {freq:.1f} 次｜累计 ¥{spend:.0f}｜意向 {r['平均意向']:.2f}｜领券 {r['领券率%']:.0f}%｜用券 {r['用券率%']:.0f}%"]
    s = []
    # 高意向群体：转化基础好，重点提客单价/频次
    if intent_tier == "高意向":
        if price < base_price:
            s.append("【提客单价·首要】该档意向强但当前客单低于大盘，主动推荐中高价升级款/套装，'满减凑单'最有效。")
        else:
            s.append("【守高客单】该档意向强且客单已高于大盘，用'买贵包退/正品保障'消除下单顾虑，维持高客单。")
        if freq < base_freq:
            s.append("【提频次】频次偏低，用'会员日/复购券/连续签到'拉回购。")
        else:
            s.append("【稳复购】频次已高，转为会员体系绑定，防流失、提LTV。")
    else:  # 低意向
        if r["领券率%"] < 15 and r["用券率%"] < 5:
            s.append("【先破冰·首单】该档基本没领过券，先用'首单立减/新人礼'吸引首次下单，建立券心智。")
        elif r["用券率%"] < 10:
            s.append("【促用券】该档领券但很少用，推送'用券倒计时+满减凑单'，把领到的券用出去。")
        else:
            s.append("【提客单】该档会领券且会用，可给'跨品类凑单券'拉高客单。")
        if r["加购率%"] < 15:
            s.append("【补内容种草】加购率低，补充'多图+视频+买家秀'提升种草→加购。")
    # 按历史价值差异化深耕
    if val_tier == "高消费":
        s.append("【VIP深耕】高历史消费，给予会员等级、专属客服、新品首发权，避免被竞品挖走。")
    elif val_tier == "低消费":
        s.append("【逐步提频】历史消费低，先以低价高性价比品促复购，积累信任后再升档推荐。")
    for t in s:
        lines.append(f"- {t}")
    strategy_lines.append("\n".join(lines))
    print("\n" + "\n".join(lines))

# ---------------- 4. 保存策略文档 ----------------
strategy_md = "# 用户价值分层与增收运营策略\n\n" \
    "> 方法：按“历史消费能力(累计消费) × 购买意向”组合成 6 类用户，避免无监督聚类无法区分消费能力的问题。\n\n" \
    f"> 大盘基准：购买率 {base_rate:.0%}，客单价 ¥{base_price:.0f}，近30天购买 {base_freq:.1f} 次。\n\n" \
    "## 分层画像\n\n" + grp[grp_cols].to_markdown(index=False) + "\n\n---\n\n## 分层运营策略\n\n" + \
    "\n\n---\n\n".join(strategy_lines)
with open(os.path.join(BASE, "output", "用户价值分层与增收策略.md"), "w", encoding="utf-8") as f:
    f.write(strategy_md)
print(f"\n策略文档已保存: output/用户价值分层与增收策略.md")

# ---------------- 5. 可视化：分层购买率/客单价横向对比 ----------------
fig, axes = plt.subplots(1, 2, figsize=(16, 6))
order = grp["分层"].tolist()
# 左：购买率 + 客单价双轴
ax1 = axes[0]
bars = ax1.bar(order, grp["购买率%"], color="#55A868", alpha=0.85, label="购买率%")
ax1.set_ylabel("购买率%")
ax1.set_ylim(0, grp["购买率%"].max() * 1.5)
ax1.axhline(base_rate * 100, ls="--", color="gray", label=f"大盘 {base_rate:.0%}")
for i, (v, p) in enumerate(zip(grp["购买率%"], grp["客单价(元)"])):
    ax1.text(i, v + 1, f"¥{p:.0f}", ha="center", fontsize=9, color="#4C72B0")
ax1.set_title("各层用户：购买率(柱) 与 客单价(顶部数字)")
ax1.tick_params(axis="x", rotation=25)
ax1.legend()
# 右：累计消费
ax2 = axes[1]
bars2 = ax2.bar(order, grp["累计消费(元)"], color="#DD8452", alpha=0.85)
ax2.set_ylabel("累计消费(元)")
ax2.set_title("各层用户：历史累计消费")
ax2.tick_params(axis="x", rotation=25)
for i, v in enumerate(grp["累计消费(元)"]):
    ax2.text(i, v + 50, f"{v:,.0f}", ha="center", fontsize=9)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "19_用户价值分层.png"), dpi=120, bbox_inches="tight")
plt.close(fig)
print("已保存: 19_用户价值分层.png")
