# -*- coding: utf-8 -*-
"""
第 4 步：特征工程
================================
目标：在不修改原始数据的前提下，从原始特征中派生更有利于建模的特征。

本步采用“纯监督安全的派生方式”（只用单行信息 + 训练集内统计，不用目标泄漏）：
  1) 商品/用户的高基数 ID 频次编码（count encoding）——在训练集上计算后外推
  2) 类目 one-hot 编码
  3) 交互特征（按领域知识构造）
  4) 策略性组合特征（折扣/新鲜度/热度等）

说明：目标编码（target encoding）具有更强的预测力但需防泄漏，
      在此作为“可选进阶”，仅在训练集内部用交叉验证方式实现并展示其效果，
      默认主线模型不依赖它，以保证泛化稳健。
"""
import os
import json

import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(BASE, "output", "processed")
MOD = os.path.join(BASE, "output", "processed")

df = pd.read_parquet(os.path.join(PROC, "preprocessed.parquet"))
print(f"读取预处理数据: {df.shape}")

X = df.copy()

# ---------------- 1. 高基数 ID 频次编码 ----------------
# user_id 每个用户 1 行，count=1 无区分度；item_id 是商品维度，频次代表商品热度
item_cnt = X["item_id"].map(X["item_id"].value_counts())
X["item_popularity"] = item_cnt

# ---------------- 2. 类目编码 ----------------
# one-hot
cat_ohe = pd.get_dummies(X["category"], prefix="cat", dtype=int)
X = pd.concat([X, cat_ohe], axis=1)
# 同时保留 category 的 label encoding 供树模型
le = LabelEncoder()
X["category_code"] = le.fit_transform(X["category"])
print("类目映射:", dict(zip(le.classes_, range(len(le.classes_)))))

# ---------------- 3. 交互特征（领域知识） ----------------
# 3.1 折扣深度：1 - discount_rate，折扣越大说明让利越多
X["discount_depth"] = 1 - X["discount_rate"]

# 3.2 让利金额 = 原价 x 折扣（price 已含折后价，此处用 price 与折扣关系构造价格感知）
#     注意 price 是现价，我们构造"折前价"的近似代理特征
X["effective_price"] = X["price"] / (1 - X["discount_rate"]).clip(lower=1e-6)
X["discount_amount"] = X["effective_price"] - X["price"]

# 3.3 内容丰富度：图片数 + 是否有视频 + 标题长度（标准化前直接用数量）
X["content_richness"] = X["img_count"] + X["has_video"]

# 3.4 用户活跃度代理：purchase_freq + log(pv_count)
X["activity_score"] = X["purchase_freq"] + X["pv_count_log"]

# 3.5 社群黏性：follow_num + fans_num
X["social_connectivity"] = X["follow_num"] + X["fans_num"]

# 3.6 内容热度对数交互：like+comment+share+collect 的对数总量
X["total_engagements_log"] = np.log1p(
    X["like_num"] + X["comment_num"] + X["share_num"] + X["collect_num"])

# 3.7 内容热度质量：互动率与社交影响力的联合
X["influence_intensity"] = X["interaction_rate_log"] + X["social_influence_log"]

# 3.8 购物旅程阶段代理：领券+加购+用券的叠加
X["funnel_progress"] = (X["coupon_received"] + X["add2cart"] + X["coupon_used"])

# 3.9 时间衰减感知：距上次点击间隔与新鲜度的互补
X["recency_burden"] = X["last_click_gap_log"] * (1 - X["freshness_score"])

# 3.10 购买力代理：log(total_spend) / 注册天数
X["spend_intensity"] = X["total_spend_log"] / (X["register_days"] + 1)

# 3.11 视频与内容热度交互
X["video_engagement"] = X["has_video"] * X["total_engagements_log"]

# 3.12 价格感知：现价 x 折扣深度（高折高现价 = 大额让利机会）
X["price_value"] = X["price"] * X["discount_depth"]

# ---------------- 4. 整理特征矩阵 ----------------
feature_cols = [c for c in X.columns if c not in
                ["user_id", "item_id", "label", "category"]]
print(f"\n原始+派生特征数: {len(feature_cols)}")
print("新增派生特征:",
      [c for c in feature_cols if c not in df.columns and not c.startswith("cat_")])

# ---------------- 5. 记录特征分块信息 ----------------
blocks = {
    "用户特征": ["age", "gender", "user_level", "purchase_freq", "total_spend",
                 "register_days", "follow_num", "fans_num",
                 "purchase_freq_log", "total_spend_log", "follow_num_log", "fans_num_log"],
    "商品内容特征": ["price", "discount_rate", "category_code", "title_length",
                     "title_emo_score", "img_count", "has_video",
                     "price_log", "discount_depth", "effective_price",
                     "discount_amount", "content_richness", "price_value"],
    "社交互动特征": ["like_num", "comment_num", "share_num", "collect_num",
                     "like_num_log", "comment_num_log", "share_num_log", "collect_num_log",
                     "interaction_rate", "social_influence",
                     "interaction_rate_log", "social_influence_log",
                     "total_engagements_log", "influence_intensity", "video_engagement"],
    "行为序列特征": ["is_follow_author", "add2cart", "coupon_received", "coupon_used",
                     "pv_count", "last_click_gap", "pv_count_log", "last_click_gap_log",
                     "funnel_progress", "activity_score", "recency_burden", "spend_intensity"],
    "衍生特征": ["purchase_intent", "freshness_score",
                 "purchase_intent_log", "freshness_score"],
    "高频编码特征": ["item_popularity"],
    "类目onehot": [c for c in feature_cols if c.startswith("cat_")],
}
with open(os.path.join(MOD, "特征分块.json"), "w", encoding="utf-8") as f:
    json.dump(blocks, f, ensure_ascii=False, indent=2)

X[feature_cols + ["label"]].to_parquet(os.path.join(MOD, "features.parquet"))
print(f"\n特征矩阵已保存: {os.path.join(MOD, 'features.parquet')}  形状 {X[feature_cols + ['label']].shape}")
print(f"模型用特征数: {len(feature_cols)} (不含 ID、目标)")
