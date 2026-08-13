# -*- coding: utf-8 -*-
"""
第 6 步：模型评估可视化
================================
生成 ROC 曲线、PR 曲线、特征重要性、混淆矩阵等评估图表。
"""
import os
import sys
import json

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, roc_auc_score, precision_recall_curve
from sklearn.model_selection import train_test_split
import xgboost as xgb
import seaborn as sns

sns.set_style("whitegrid")
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans SC", "sans-serif"]
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.unicode_minus"] = False

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_utils import check_overlap

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(BASE, "output", "processed")
MOD = os.path.join(BASE, "output", "models")
FIG = os.path.join(BASE, "output", "figures")
os.makedirs(FIG, exist_ok=True)

X = pd.read_parquet(os.path.join(PROC, "features.parquet"))
y = X["label"].values
FEATS = [c for c in X.columns if c != "label"]
# 与建模脚本保持一致：按 label × user_level 组合分层
strat_keys = (X["label"].astype(str) + "_" + X["user_level"].astype(str)).values
X_train, X_test, y_train, y_test = train_test_split(
    X[FEATS], y, test_size=0.2, stratify=strat_keys, random_state=42)

# 加载已训练模型
xgb_model = xgb.XGBClassifier()
xgb_model.load_model(os.path.join(MOD, "xgb_model.json"))
proba = xgb_model.predict_proba(X_test)[:, 1]
y_true = y_test

# ---------------- 1. ROC 曲线 ----------------
fpr, tpr, _ = roc_curve(y_true, proba)
auc = roc_auc_score(y_true, proba)
fig, ax = plt.subplots(figsize=(7, 6))
ax.plot(fpr, tpr, lw=2, color="#4C72B0", label=f"XGBoost (AUC={auc:.4f})")
ax.plot([0, 1], [0, 1], ls="--", color="gray", label="随机基线 (AUC=0.5)")
ax.set_xlabel("假正率 (FPR)")
ax.set_ylabel("真正率 (TPR)")
ax.set_title(f"ROC 曲线 —— XGBoost 购买预测 (AUC={auc:.4f})")
ax.legend(loc="lower right")
fig.tight_layout()
check_overlap(fig, "14_ROC曲线.png")
fig.savefig(os.path.join(FIG, "14_ROC曲线.png"), dpi=120, bbox_inches="tight")
plt.close(fig)
print("已保存: 14_ROC曲线.png")

# ---------------- 2. PR 曲线 ----------------
precision, recall, _ = precision_recall_curve(y_true, proba)
base_rate = y_true.mean()
fig, ax = plt.subplots(figsize=(7, 6))
ax.plot(recall, precision, lw=2, color="#55A868",
        label=f"XGBoost (PR-AUC={auc:.4f})")
ax.axhline(base_rate, ls="--", color="gray",
           label=f"全局购买率基线 ({base_rate:.3f})")
ax.set_xlabel("召回率 (Recall)")
ax.set_ylabel("精确率 (Precision)")
ax.set_title("Precision-Recall 曲线")
ax.legend(loc="upper right")
fig.tight_layout()
check_overlap(fig, "15_PR曲线.png")
fig.savefig(os.path.join(FIG, "15_PR曲线.png"), dpi=120, bbox_inches="tight")
plt.close(fig)
print("已保存: 15_PR曲线.png")

# ---------------- 3. 特征重要性 Top 15 ----------------
imp = pd.read_csv(os.path.join(MOD, "特征重要性.csv")).head(15).iloc[::-1]
fig, ax = plt.subplots(figsize=(9, 7))
ax.barh(imp["特征"], imp["重要性"], color="#DD8452")
ax.set_xlabel("特征重要性 (gain)")
ax.set_title("XGBoost 特征重要性 Top 15")
fig.tight_layout()
check_overlap(fig, "16_特征重要性.png")
fig.savefig(os.path.join(FIG, "16_特征重要性.png"), dpi=120, bbox_inches="tight")
plt.close(fig)
print("已保存: 16_特征重要性.png")

# ---------------- 4. 混淆矩阵 (最优阈值) ----------------
with open(os.path.join(MOD, "最优阈值.json"), "r", encoding="utf-8") as f:
    thr = json.load(f)["最优阈值"]
pred = (proba >= thr).astype(int)
from sklearn.metrics import confusion_matrix
cm = confusion_matrix(y_true, pred)
fig, ax = plt.subplots(figsize=(6, 5.5))
sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False,
            xticklabels=["预测未购买", "预测购买"],
            yticklabels=["实际未购买", "实际购买"], ax=ax)
ax.set_title(f"混淆矩阵 (最优阈值={thr})")
fig.tight_layout()
check_overlap(fig, "17_混淆矩阵.png")
fig.savefig(os.path.join(FIG, "17_混淆矩阵.png"), dpi=120, bbox_inches="tight")
plt.close(fig)
print("已保存: 17_混淆矩阵.png")

# ---------------- 5. 阈值 - 指标曲线 ----------------
prec, rec, thrs = precision_recall_curve(y_true, proba)
f1s = 2 * prec * rec / np.clip(prec + rec, 1e-9, None)
fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(thrs, prec[:-1], label="Precision", color="#C44E52")
ax.plot(thrs, rec[:-1], label="Recall", color="#4C72B0")
ax.plot(thrs, f1s[:-1], label="F1", color="#55A868", lw=2)
ax.axvline(thr, ls="--", color="gray", label=f"最优阈值={thr}")
ax.set_xlabel("判定阈值")
ax.set_ylabel("指标值")
ax.set_title("阈值 vs 精确率/召回率/F1")
ax.legend()
fig.tight_layout()
check_overlap(fig, "18_阈值曲线.png")
fig.savefig(os.path.join(FIG, "18_阈值曲线.png"), dpi=120, bbox_inches="tight")
plt.close(fig)
print("已保存: 18_阈值曲线.png")

print("\n评估图表生成完毕。")
