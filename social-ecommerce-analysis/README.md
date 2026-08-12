# 社交电商用户购买行为预测 —— 全流程数据分析项目

对一份 **100,000 条** 社交电商用户购买行为记录（小红书/抖音类平台真实场景）进行完整的
**数据探索 → 预处理 → 特征工程 → 建模评估 → 运营建议** 分析。

> 数据集来源：https://tianchi.aliyun.com/dataset/215680?accounttraceid=c5d1404137424fb1a28d5e71ad541c7dhdnb
> social_ecommerce_data.csv`（**只读，本项目不做任何修改**）。

---

## 项目结构

```
social-ecommerce-analysis/
├── README.md                        # 本文件
├── scripts/
│   ├── 01_data_overview.py          # 数据概览与质量检查
│   ├── 02_eda.py                    # 探索性数据分析（分布/相关性/分群购买率）
│   ├── 03_preprocessing.py          # 预处理（缺失检查、异常探测、log1p 变换）
│   ├── 04_feature_engineering.py    # 特征工程（派生 15 个特征）
│   ├── 05_modeling.py               # 建模（LR / RF / XGBoost + 调参 + 阈值优化 + 画像）
│   ├── 06_eval_plots.py             # 模型评估可视化（ROC/PR/重要性/混淆矩阵）
│   └── 07_generate_report.py        # 自动生成 Markdown 分析报告
└── output/
    ├── 数据分析报告.md               # 最终交付报告（含全部结论与建议）
    ├── overview/                    # 数据概览表（分布、统计、相关性）
    ├── figures/                     # 18 张分析图表
    ├── processed/                   # 预处理与特征矩阵（parquet）
    └── models/                      # 模型文件、评估结果、特征重要性、画像
```

## 快速开始

```bash
# 依次执行（或单独执行任意一步）
python scripts/01_data_overview.py
python scripts/02_eda.py
python scripts/03_preprocessing.py
python scripts/04_feature_engineering.py
python scripts/05_modeling.py
python scripts/06_eval_plots.py
python scripts/07_generate_report.py
```

依赖：`pandas numpy scikit-learn matplotlib seaborn xgboost`（tabulate 用于生成报告表格）。
若控制台中文显示乱码，可加环境变量 `PYTHONIOENCODING=utf-8`（不影响输出文件）。

## 关键结论速览

| 项目 | 结论 |
|---|---|
| 数据质量 | 无缺失、无重复，逻辑一致性通过 |
| 目标分布 | 正样本 **44.98%**（与描述"约 1:4"不符，实测近似均衡 1:1.22） |
| 用户画像 | 平均年龄 27.1，女性 63.7%，年轻女性为主 |
| 最强信号 | `add2cart`（相关系数 0.36，XGB 重要性 45.6%）等行为序列特征 |
| 最佳模型 | XGBoost 测试集 AUC **0.7754** |
| 阈值优化 | 阈值 0.329 下 F1 **0.691**（默认 0.5 时 0.658） |
| 运营圈选 | 预测 Top 20% 群体实际购买率 **82.8%**，为全局的 1.8 倍 |

## 运行环境

- Python 3.12.7（Anaconda）
- pandas 3.0.3 / numpy 2.2.6 / scikit-learn 1.9.0 / xgboost 3.3.0
- matplotlib 3.11.0 / seaborn 0.13.2

## 注意事项

1. 所有脚本均以**只读**方式访问原始 CSV，加工结果只写入 `output/` 目录。
2. 建模采用 80/20 分层划分 + 固定随机种子（42），结果可复现。
3. `add2cart` 等行为特征预测力最强，但业务部署时需注意时间窗设定，避免特征泄漏。
4. 详细分析见 **[output/数据分析报告.md](output/数据分析报告.md)**。
