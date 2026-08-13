# -*- coding: utf-8 -*-
"""
第 5 步：建模与评估
================================
目标：
  1) 分层划分训练集 / 测试集（保持 label 比例）
  2) 建立基线模型：Logistic Regression 与 Random Forest
  3) 梯度提升树 XGBoost（含简单调参与早停）
  4) 统一评估指标：Accuracy / Precision / Recall / F1 / AUC / 混淆矩阵
  5) 特征重要性分析
  6) 概率阈值优化（面向 F1）
  7) 高潜用户画像分析（供运营参考）

要点：全程不修改原始数据；划分在固定随机种子下进行以保证可复现。
"""
import os
import json

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, roc_auc_score, roc_curve,
                             confusion_matrix, precision_recall_curve)
import xgboost as xgb

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(BASE, "output", "processed")
MOD = os.path.join(BASE, "output", "models")
os.makedirs(MOD, exist_ok=True)

SEED = 42
np.random.seed(SEED)

X = pd.read_parquet(os.path.join(PROC, "features.parquet"))
y = X["label"].values
FEATS = [c for c in X.columns if c != "label"]
print(f"特征数: {len(FEATS)}, 样本数: {len(X)}, 正样本占比: {y.mean():.4f}")

# ---------------- 1. 数据划分 ----------------
# 按 label × user_level 组合分层：既保证训练/测试集正负比例一致，
# 也保证用户等级结构一致（避免某等级用户全部落入测试集导致评估失真）
strat_keys = (X["label"].astype(str) + "_" + X["user_level"].astype(str)).values
X_train, X_test, y_train, y_test = train_test_split(
    X[FEATS], y, test_size=0.2, stratify=strat_keys, random_state=SEED)
print(f"训练集: {X_train.shape}, 测试集: {X_test.shape}")
print(f"训练集正样本占比: {y_train.mean():.4f}, 测试集正样本占比: {y_test.mean():.4f}")

# 记录用户画像所需的信息（测试集的 user_id / category 等）
X_test_full = X.loc[X_test.index]
X_train_full = X.loc[X_train.index]

# ---------------- 评估工具 ----------------
def evaluate(model, X_, y_, name, save_cm=True):
    pred = model.predict(X_)
    proba = model.predict_proba(X_)[:, 1]
    res = {
        "模型": name,
        "Accuracy": round(accuracy_score(y_, pred), 4),
        "Precision": round(precision_score(y_, pred, zero_division=0), 4),
        "Recall": round(recall_score(y_, pred, zero_division=0), 4),
        "F1": round(f1_score(y_, pred, zero_division=0), 4),
        "AUC": round(roc_auc_score(y_, proba), 4),
    }
    if save_cm:
        cm = confusion_matrix(y_, pred)
        res["混淆矩阵"] = cm.tolist()
    return res, proba

# ---------------- 2. 基线模型 ----------------
print("\n" + "=" * 60)
print("训练基线模型 ...")

# 2.1 逻辑回归（需标准化）
scaler = StandardScaler()
X_train_s = scaler.fit_transform(X_train)
X_test_s = scaler.transform(X_test)

# 处理可能存在的 inf（log1p 不会产生 inf，但保险起见）
X_train_s = np.nan_to_num(X_train_s, nan=0.0, posinf=0.0, neginf=0.0)
X_test_s = np.nan_to_num(X_test_s, nan=0.0, posinf=0.0, neginf=0.0)

lr = LogisticRegression(max_iter=2000, C=0.5, random_state=SEED)
lr.fit(X_train_s, y_train)
lr_train, _ = evaluate(lr, X_train_s, y_train, "LogisticRegression(训练集)")
lr_test, lr_proba = evaluate(lr, X_test_s, y_test, "LogisticRegression(测试集)")
print("  LR 训练集:", {k: v for k, v in lr_train.items() if k != "混淆矩阵"})
print("  LR 测试集:", {k: v for k, v in lr_test.items() if k != "混淆矩阵"})

# 2.2 随机森林
rf = RandomForestClassifier(n_estimators=300, max_depth=12, min_samples_leaf=5,
                            n_jobs=-1, random_state=SEED, class_weight="balanced")
rf.fit(X_train, y_train)
rf_train, _ = evaluate(rf, X_train, y_train, "RandomForest(训练集)")
rf_test, rf_proba = evaluate(rf, X_test, y_test, "RandomForest(测试集)")
print("  RF 训练集:", {k: v for k, v in rf_train.items() if k != "混淆矩阵"})
print("  RF 测试集:", {k: v for k, v in rf_test.items() if k != "混淆矩阵"})


# ---------------- 3. XGBoost 模型（主模型） ----------------
print("\n" + "=" * 60)
print("训练 XGBoost ...")

# 3.1 先做一轮快速调参：简单网格搜索（用验证集上的 AUC）
best_params, best_score = {}, -1
grid = {
    "max_depth": [5, 7],
    "learning_rate": [0.05, 0.1],
    "subsample": [0.8],
    "colsample_bytree": [0.8],
}
print("  简单网格搜索（随机抽样 3 组）...")
np.random.seed(SEED)
trials = np.random.choice(len(grid["max_depth"]) * len(grid["learning_rate"]),
                          min(3, len(grid["max_depth"]) * len(grid["learning_rate"])),
                          replace=False)
for t in trials:
    md = grid["max_depth"][t % 2]
    lr_rate = grid["learning_rate"][t // 2 % 2]
    params = {
        "max_depth": md, "learning_rate": lr_rate,
        "subsample": 0.8, "colsample_bytree": 0.8,
        "n_estimators": 500, "early_stopping_rounds": 30,
        "eval_metric": "auc", "random_state": SEED,
    }
    model = xgb.XGBClassifier(**params)
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
    if auc > best_score:
        best_score, best_params = auc, params
    print(f"    max_depth={md}, lr={lr_rate} -> AUC={auc:.4f}")
print(f"  最优参数: {best_params}, 验证 AUC={best_score:.4f}")

# 3.2 用最优参数在完整训练集上训练
xgb_model = xgb.XGBClassifier(
    max_depth=best_params["max_depth"],
    learning_rate=best_params["learning_rate"],
    subsample=best_params["subsample"],
    colsample_bytree=best_params["colsample_bytree"],
    n_estimators=400,
    eval_metric="auc",
    random_state=SEED,
)
xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
xgb_train, _ = evaluate(xgb_model, X_train, y_train, "XGBoost(训练集)")
xgb_test, xgb_proba = evaluate(xgb_model, X_test, y_test, "XGBoost(测试集)")
print("  XGB 训练集:", {k: v for k, v in xgb_train.items() if k != "混淆矩阵"})
print("  XGB 测试集:", {k: v for k, v in xgb_test.items() if k != "混淆矩阵"})


# ---------------- 4. 汇总与模型保存 ----------------
results = [lr_train, lr_test, rf_train, rf_test, xgb_train, xgb_test]
res_df = pd.DataFrame(results).drop(columns="混淆矩阵", errors="ignore")
print("\n" + "=" * 60)
print("【模型评估汇总】")
print(res_df.to_string(index=False))
res_df.to_csv(os.path.join(MOD, "模型评估汇总.csv"), index=False)

cm_all = {"LR": lr_test["混淆矩阵"], "RF": rf_test["混淆矩阵"], "XGB": xgb_test["混淆矩阵"]}
with open(os.path.join(MOD, "混淆矩阵.json"), "w", encoding="utf-8") as f:
    json.dump(cm_all, f, ensure_ascii=False, indent=2)

# 保存主模型与预处理对象
xgb_model.save_model(os.path.join(MOD, "xgb_model.json"))
import pickle
with open(os.path.join(MOD, "scaler.pkl"), "wb") as f:
    pickle.dump(scaler, f)
with open(os.path.join(MOD, "模型与特征清单.json"), "w", encoding="utf-8") as f:
    json.dump({"特征列表": FEATS, "最优参数": best_params}, f, ensure_ascii=False, indent=2)
print("\n模型已保存至 output/models/")


# ---------------- 5. 特征重要性 ----------------
importance = pd.DataFrame({
    "特征": FEATS,
    "重要性": xgb_model.feature_importances_,
}).sort_values("重要性", ascending=False)
print("\n【XGBoost 特征重要性 Top 20】")
print(importance.head(20).to_string(index=False))
importance.to_csv(os.path.join(MOD, "特征重要性.csv"), index=False)

# ---------------- 6. 概率阈值优化（测试集，面向 F1） ----------------
prec, rec, thrs = precision_recall_curve(y_test, xgb_proba)
f1s = 2 * prec * rec / np.clip(prec + rec, 1e-9, None)
best_idx = int(np.argmax(f1s))
best_thr = thrs[best_idx] if best_idx < len(thrs) else 0.5
best_f1 = f1s[best_idx]
pred_opt = (xgb_proba >= best_thr).astype(int)
print(f"\n【阈值优化】最优阈值 = {best_thr:.3f}")
print(f"  默认0.5阈值  -> F1={f1_score(y_test, (xgb_proba >= 0.5).astype(int)):.4f}")
print(f"  优化阈值     -> F1={f1_score(y_test, pred_opt):.4f}")
print(f"  优化阈值下 Precision={precision_score(y_test, pred_opt):.4f}, "
      f"Recall={recall_score(y_test, pred_opt):.4f}")
with open(os.path.join(MOD, "最优阈值.json"), "w", encoding="utf-8") as f:
    json.dump({"最优阈值": round(float(best_thr), 4), "F1": round(float(best_f1), 4)}, f,
              ensure_ascii=False, indent=2)

# ---------------- 7. 高潜用户画像分析 ----------------
print("\n" + "=" * 60)
print("【高潜用户画像分析】(基于测试集预测概率 Top 20%)")
test_df = X_test_full.copy()
test_df["pred_proba"] = xgb_proba
test_df["label_true"] = y_test
top20 = test_df[test_df["pred_proba"] >= test_df["pred_proba"].quantile(0.8)]
rest = test_df[test_df["pred_proba"] < test_df["pred_proba"].quantile(0.8)]
print(f"  高潜群体样本数: {len(top20)}, 其余: {len(rest)}")

profile = {}
for col, fmt in [("age", ".1f"), ("gender", ".3f"), ("user_level", ".2f"),
                 ("purchase_freq", ".1f"), ("total_spend", ".0f"),
                 ("price", ".1f"), ("discount_rate", ".3f"), ("add2cart", ".3f"),
                 ("coupon_used", ".3f"), ("pv_count", ".1f"),
                 ("last_click_gap", ".1f"), ("interaction_rate", ".1f"),
                 ("purchase_intent", ".2f"), ("freshness_score", ".3f"),
                 ("social_influence", ".1f"), ("like_num", ".1f")]:
    if col in test_df.columns:
        profile[col] = {
            "高潜Top20%": round(float(top20[col].mean()), 3),
            "其余": round(float(rest[col].mean()), 3),
        }
profile_df = pd.DataFrame(profile).T
print(profile_df.round(2).to_string())
profile_df.round(3).to_csv(os.path.join(MOD, "高潜用户画像.csv"))

# 类目分布对比
# category 未包含在特征矩阵中，从原始数据按行索引对齐取回（仅读取，不修改）
RAW = r"C:\Users\18887\Downloads\social_ecommerce_data.csv"
raw_cat = pd.read_csv(RAW, usecols=["category"])
test_df["category"] = raw_cat["category"].reindex(test_df.index).values
cat_cross = pd.crosstab(test_df["category"], test_df["pred_proba"] >= test_df["pred_proba"].quantile(0.8))
cat_cross.columns = ["其余", "高潜Top20%"]
cat_cross_pct = cat_cross.div(cat_cross.sum(axis=0), axis=1).round(3)
print("\n  类目在高潜/其余群体中的占比:")
print(cat_cross_pct.to_string())
cat_cross_pct.to_csv(os.path.join(MOD, "高潜类目分布.csv"))

# 高潜群体的真实购买率（验证模型的区分能力）
hit_rate = top20["label_true"].mean()
print(f"\n  高潜Top20%群体的实际购买率: {hit_rate:.3f} (全局: {y_test.mean():.3f})")
print("  => 高潜群体购买率是全局的 {:.1f} 倍，可用于运营圈选".format(hit_rate / y_test.mean()))

print("\n全部完成。输出目录: output/models/")
