# -*- coding: utf-8 -*-
"""
第 3 步：数据预处理
================================
目标：
  1) 缺失值 / 重复值 / 异常值检查（此数据集经核实无缺失、无重复）
  2) 右偏连续特征做 log1p 变换
  3) 高基数类别特征（user_id, item_id）保留供特征工程阶段做频次编码
  4) 输出预处理后的数据集（只保存到 output/processed，绝不修改原始数据）

要点：本脚本的输入是原始 CSV 的只读副本，所有修改仅作用于内存中的副本。
"""
import os
import json

import pandas as pd
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = r"C:\Users\18887\Downloads\social_ecommerce_data.csv"
PROC = os.path.join(BASE, "output", "processed")
os.makedirs(PROC, exist_ok=True)

df = pd.read_csv(RAW)
print(f"读取原始数据: {df.shape}")

# ---------------- 1. 缺失与重复检查 ----------------
missing = df.isna().sum()
assert missing.sum() == 0, f"存在缺失值: {missing[missing > 0]}"
print("缺失值: 0 ✅")
assert df.duplicated().sum() == 0, "存在重复行"
print("重复行: 0 ✅")

# ---------------- 2. 逻辑一致性检查 ----------------
# 2.1 折扣率范围 0~1
assert df["discount_rate"].between(0, 1).all(), "discount_rate 超出 [0,1]"
# 2.2 情感得分范围 0~1
assert df["title_emo_score"].between(0, 1).all(), "title_emo_score 超出 [0,1]"
# 2.3 二值字段取值检查
for col in ["gender", "has_video", "is_follow_author", "add2cart",
            "coupon_received", "coupon_used", "label"]:
    uniq = sorted(df[col].unique())
    assert set(uniq) <= {0, 1}, f"{col} 取值超出 {{0,1}}: {uniq}"
print("逻辑一致性检查通过 ✅")

# ---------------- 3. 数值型异常值探测（用 IQR 法，仅报告不删除） ----------------
num_cols = df.select_dtypes(include=["number"]).columns.tolist()
report = {}
for c in num_cols:
    if c == "label":
        continue
    q1, q3 = df[c].quantile([0.25, 0.75])
    iqr = q3 - q1
    if iqr > 0:
        ub = q3 + 3 * iqr
        lb = q1 - 3 * iqr
        n_out = int(((df[c] < lb) | (df[c] > ub)).sum())
        report[c] = {"下界": round(lb, 2), "上界": round(ub, 2), "疑似异常数": n_out,
                     "异常占比%": round(n_out / len(df) * 100, 2)}
print("\n【IQR 3 倍区间法异常值探测】(仅报告，保留原值)")
for c, v in report.items():
    print(f"  {c:<18} 疑似异常 {v['疑似异常数']:>6}  ({v['异常占比%']:.2f}%)")
with open(os.path.join(PROC, "异常值探测报告.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

# ---------------- 4. 右偏特征 log1p 变换 ----------------
# 说明：以下特征偏度普遍很高（点赞/评论/分享/收藏、互动率、消费、价格、浏览等），
#       对树模型影响不大，但对线性/距离类模型和后续特征工程显著有利。统一做 log1p。
skewed_cols = [
    "purchase_freq", "total_spend", "follow_num", "fans_num", "price",
    "like_num", "comment_num", "share_num", "collect_num",
    "pv_count", "last_click_gap", "interaction_rate", "purchase_intent",
    "social_influence",
]
df_pre = df.copy()
for c in skewed_cols:
    df_pre[c + "_log"] = np.log1p(df_pre[c])

print(f"\n已对 {len(skewed_cols)} 个右偏特征生成 log1p 变换列")
print("变换后偏度对比：")
for c in skewed_cols:
    before = df[c].skew()
    after = df_pre[c + "_log"].skew()
    print(f"  {c:<18} 偏度 {before:>8.2f} -> {after:>8.2f}")

# ---------------- 5. 类别特征处理说明 ----------------
# category：6 个类目的低基数类别 → 特征工程阶段做 one-hot / target encoding
# user_id / item_id：高基数（100000 / 60363）→ 特征工程阶段做频次编码（count encoding）
print(f"\n类目数: {df['category'].nunique()}")
print(f"user_id 唯一值: {df['user_id'].nunique()}")
print(f"item_id 唯一值: {df['item_id'].nunique()}")

# ---------------- 6. 保存预处理结果 ----------------
# 保存列清单，供特征工程/建模阶段引用
with open(os.path.join(PROC, "列清单.json"), "w", encoding="utf-8") as f:
    json.dump(
        {"原始列": list(df.columns),
         "log变换列": [c + "_log" for c in skewed_cols],
         "右偏原始列": skewed_cols},
        f, ensure_ascii=False, indent=2)

df_pre.to_parquet(os.path.join(PROC, "preprocessed.parquet"))
print(f"\n预处理数据已保存: {os.path.join(PROC, 'preprocessed.parquet')}")
print(f"维度: {df_pre.shape}")
