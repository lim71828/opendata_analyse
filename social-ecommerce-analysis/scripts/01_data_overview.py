# -*- coding: utf-8 -*-
"""
第 1 步：数据概览与质量检查
================================
目的：读入原始数据，了解数据规模、字段类型、缺失情况、重复情况、
目标变量分布与基本统计量，为后续分析把好第一道关。

要点：本脚本只读不写，不对原始数据集做任何修改。
"""
import os
import sys
import json

import pandas as pd
import numpy as np

# ---------------- 路径配置 ----------------
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = r"C:\Users\18887\Downloads\social_ecommerce_data.csv"
OUT = os.path.join(BASE, "output", "overview")
os.makedirs(OUT, exist_ok=True)

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 40)

# ---------------- 1. 数据读取 ----------------
print("=" * 70)
print("读取原始数据 ...")
df = pd.read_csv(RAW)  # 注意：数据包含 BOM 表头，pandas 自动处理
print(f"数据集规模: {df.shape[0]:,} 行 × {df.shape[1]:,} 列")

# ---------------- 2. 基本信息 ----------------
dtypes = pd.DataFrame(
    {
        "字段": df.columns,
        "类型": df.dtypes.astype(str).values,
        "非空数": df.notna().sum().values,
        "缺失数": df.isna().sum().values,
        "缺失率(%)": (df.isna().mean() * 100).round(3).values,
        "唯一值数": df.nunique().values,
    }
)
print("\n【字段信息 / 缺失情况】")
print(dtypes.to_string(index=False))
dtypes.to_csv(os.path.join(OUT, "字段信息与缺失统计.csv"), index=False)

# ---------------- 3. 重复记录检查 ----------------
dup = df.duplicated().sum()
print(f"\n【重复检查】完全重复行数: {dup:,}")

# ---------------- 4. 目标变量分布 ----------------
label_counts = df["label"].value_counts().sort_index()
label_pct = (df["label"].value_counts(normalize=True).sort_index() * 100).round(2)
print("\n【目标变量 label(是否购买)分布】")
dist = pd.DataFrame({"数量": label_counts, "占比(%)": label_pct})
print(dist.to_string())
dist.to_csv(os.path.join(OUT, "目标变量分布.csv"))

# ---------------- 5. 数值列统计量 ----------------
num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
cat_cols = df.select_dtypes(include=["object"]).columns.tolist()
print(f"\n数值型列: {len(num_cols)} 个")
print(f"分类型列: {len(cat_cols)} 个 -> {list(cat_cols)}")

stats = df[num_cols].describe().T
stats["偏度"] = df[num_cols].skew().round(3)
stats["峰度"] = df[num_cols].kurt().round(3)
stats = stats.round(3)
print("\n【数值列统计量(含偏度/峰度)】")
print(stats.to_string())
stats.to_csv(os.path.join(OUT, "数值列描述统计.csv"))

# ---------------- 6. 分类型列取值分布 ----------------
for c in cat_cols:
    vc = df[c].value_counts()
    top = vc.head(10)
    print(f"\n【分类列 {c}】唯一值 {len(vc)} 个, Top10:")
    for k, v in top.items():
        print(f"   {k:<10} {v:>8,}  ({v / len(df) * 100:.2f}%)")

# ---------------- 7. 汇总存档 ----------------
summary = {
    "rows": int(len(df)),
    "cols": int(len(df.columns)),
    "duplicates": int(dup),
    "missing_total": int(df.isna().sum().sum()),
    "pos_rate": float(round((df["label"] == 1).mean(), 4)),
    "age_mean": float(df["age"].mean().round(2)),
    "female_ratio": float(round((df["gender"] == 0).mean(), 4)),
    "num_cols": int(len(num_cols)),
    "cat_cols": int(len(cat_cols)),
}
with open(os.path.join(OUT, "概览摘要.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print("\n" + "=" * 70)
print(f"完成。结果已保存至: {OUT}")
print(json.dumps(summary, ensure_ascii=False, indent=2))
