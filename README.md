# opendata_analyse

- 项目主要使用的编程语言是 python

## list
一.[社交电商分析](https://github.com/lim71828/opendata_analyse/blob/main/social-ecommerce-analysis/output/%E6%95%B0%E6%8D%AE%E5%88%86%E6%9E%90%E6%8A%A5%E5%91%8A.md)  
1.1 项目描述：基于10万条社交电商用户数据构建购买预测模型,XGBoost最优,AUC达0.775。加购、领券、用券为最强信号,高潜用户购买率达82.8%。建议优先对加购未购用户推送限时券,缩短决策周期,提升转化。  
1.2 项目流程：数据概览 → 检查数据质量与分布 EDA → 探索特征与购买关系 预处理+特征工程 → 变换、派生 63 个特征 建模 → LR/RF/XGBoost 对比与调优 报告 → 输出结论与运营建议[具体](https://github.com/lim71828/opendata_analyse/blob/main/social-ecommerce-analysis/README.md)  
二[客户流失数据]  
2.1项目描述：本项目基于银行客户行为数据构建流失预测模型，经特征工程与机器学习建模识别高风险客户，制定分层挽留策略，帮助企业降低流失、提升留存与长期价值。  
2.2项目流程：先看清数据、剔除无用字段、加工特征，再划分样本、训练多个模型选出最优，最后依据流失概率对客户分层并制定挽留策略。
