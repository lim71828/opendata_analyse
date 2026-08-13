# 电商交易数据 MySQL 分析方案

> 配套可执行脚本：`taobao_mysql_analysis.sql`（按顺序执行即可）
> 数据文件：`淘宝用户行为.csv`（99,458 行含表头，即 99,457 条交易记录）

---

## 前言｜业务背景与痛点（先定义问题，再定分析）

### 业务背景
本方案面向一家**综合类目电商平台（自营）**：经营 8 大类目商品（服饰、美妆、食品饮料、鞋类、玩具、数码科技、图书、纪念品），覆盖 2021-01 ~ 2023-03 三年周期，拥有约 9.9 万注册客户。平台处于"增量放缓、需精细化运营"阶段，管理层希望在**不新增流量投入**的前提下，靠存量客户的经营提效拉动营收。

### 核心业务痛点（5 个）

| # | 业务痛点 | 现状问题 | 期望决策 |
|---|---|---|---|
| P1 | 客户价值不透明 | 营销费用"撒胡椒面"，高价值客户识别不出 | 识别高/中/低价值客群，定向配置权益 |
| P2 | 货盘与资源分配靠经验 | 不清楚哪些类目是营收主力、哪些是高客单提升点 | 明确类目结构，指导选品与资源倾斜 |
| P3 | 人货错配 | 不同性别/年龄段的类目偏好未知，推荐和活动没依据 | 建立"人群×类目"偏好矩阵 |
| P4 | 客单价与支付无策略 | 价格带结构不清晰，支付渠道是否影响客单未知 | 定价门槛、支付渠道运营建议 |
| P5 | 备货与促销节奏被动 | 销售季节性波动不明，备货和活动日历凭经验 | 识别月度/周内周期，指导备货与排期 |

### 痛点 → 分析主题 → 决策建议（方案设计主线）

| 业务痛点 | 对应分析主题 | 决策建议输出 |
|---|---|---|
| P1 | STEP 7 客户价值分层 + 二八法则验证 | 高价值客群画像 → 定向权益/专属活动 |
| P2 | 6.2 类目结构分析 / 6.4 价格带 | 营收主力类目 → 资源倾斜；高客单类目 → 重点提升 |
| P3 | 6.3 用户画像 × 类目交叉 | 人群偏好矩阵 → 精准推荐/活动选品 |
| P4 | 6.4 价格带 / 6.5 支付分析 | 满减门槛、支付渠道运营策略 |
| P5 | 6.6 时间趋势分析 | 备货计划、促销日历 |

> **设计原则**：STEP 6 的六大分析主题不是"有什么字段就分析什么"，而是**由上述痛点倒推**——每个主题必须对应至少一个业务决策，没有对应决策的分析一律不做。

---

## 0. 数据核查结论（先看这条）

### 0.1 实际字段结构与"淘宝用户行为"描述的差异

| 描述中声称的字段 | 数据里实际情况 |
|---|---|
| 用户 ID | ✅ 有：`customer_id` |
| 商品 ID | ❌ 没有商品 SKU，只有 `invoice_no`（发票/订单号） |
| 商品类目 | ✅ 有：`category`（8 个类目） |
| 行为类型（pv/cart/fav/buy） | ❌ 没有——每条记录本身就是一笔交易 |
| 时间戳 | ⚠️ 有日期 `invoice_date`（2021/1/1 ~ 2023/3/8），无时分秒 |

**结论：这不是阿里天池 `UserBehavior` 那种"浏览/加购/收藏/购买行为序列"数据，而是一份发票级订单交易明细数据。** 字段为：`invoice_no, customer_id, gender, age, category, quantity, price, payment_method, invoice_date`。

### 0.2 更关键的结构限制

经全量核查：

- 数据行数 = **99,457**
- 唯一 `customer_id` 数 = **99,457**（每个用户恰好出现一次）
- 唯一 `invoice_no` 数 = **99,457**（每个订单恰好一行）

即：**每个用户只有一笔交易、每个订单只有一个商品类目行**。这意味着——

| 分析目标 | 是否可行 | 原因 |
|---|---|---|
| 复购分析 / 用户生命周期 / RFM（R 值） | ❌ 不可行 | 每用户仅一条记录，无历史行为 |
| 行为漏斗（浏览→加购→购买） | ❌ 不可行 | 无行为类型字段 |
| 订单内关联规则（Apriori） | ❌ 不可行 | 每订单仅一个类目行 |
| 类目 × 人群交叉分析 | ✅ 可行 | 本方案核心 |
| 单次消费价值分层 / 用户画像聚类 | ✅ 可行 | 可基于人口属性+消费特征分群 |
| 商品类目 / 价格 / 支付偏好 | ✅ 可行 | 维度完整 |
| 销售时间趋势 | ✅ 可行 | 日期完整 |

> 如果你的真实目标是"浏览/加购/收藏行为序列挖掘"，需要换用阿里天池 UserBehavior 数据集（字段为 `user_id,item_id,category_id,behavior_type,timestamp`）。本方案按现有交易数据设计。

### 0.3 数据基本画像（已实测）

- 8 个类目：Clothing(30,771)、Food & Beverage(15,865)、Cosmetics(15,097)、Toys(10,087)、Shoes(10,034)、Technology(7,623)、Souvenir(4,999)、Books(4,981)
- 3 种支付：Card(44,447)、Alipay(34,931)、WeChat Pay(20,079)
- 性别：Female 57,832 / Male 41,625
- 年龄：18 ~ 69，均值约 43
- 价格、类目字段无脏值（已核验），行尾有 5 个空逗号残留需清理

---

## 1. 总体流程（7 步）

```
CSV 预处理 → 建库建表 → 导入(LOAD DATA) → 数据质量检查 → 描述性统计 → 六大主题分析 → 客户分群与进阶建模
```

---

## 2. Step 1｜CSV 预处理（导入前必做）

原始 CSV 每行结尾带 `,,,,,`（5 个空逗号），需先清理，否则 LOAD DATA 会报字段列数不符。

> ⚠️ 实测：本 CSV 为 **CRLF 行尾**（`\r\n`），且每行尾带 `,,,,,`，两条都必须处理。注意：直接用 `s/,*$//` 在 CRLF 文件上会因 `\r` 挡在行尾而**失效**。

**方案 A（推荐，命令行，同时处理 CRLF 与空逗号）：**
```bash
sed -i 's/\r$//; s/,*$//' 淘宝用户行为.csv
```
> 效果：先把 `\r` 去掉（CRLF→LF），再把行尾空逗号清理。最终为 LF + 干净行尾，与脚本 `LINES TERMINATED BY '\n'` 匹配。

**方案 B（编辑器）**：Notepad++ / VS Code 打开，正则 `,+$` 替换为空，并把 EOL 统一为 LF。

> 建议复制一份原始文件后再处理。

---

## 3. Step 2｜建库建表

```sql
CREATE DATABASE IF NOT EXISTS taobao_analysis DEFAULT CHARSET utf8mb4;
USE taobao_analysis;

CREATE TABLE t_raw (
  invoice_no    VARCHAR(20),   -- 订单号
  customer_id   VARCHAR(20),   -- 客户ID
  gender        VARCHAR(10),   -- 性别
  age           INT,           -- 年龄
  category      VARCHAR(30),   -- 商品类目
  quantity      INT,           -- 数量
  price         DECIMAL(10,2), -- 单价
  payment_method VARCHAR(20),  -- 支付方式
  invoice_date  VARCHAR(10)    -- 日期(先按字符串导入，再转DATE)
);
```

设计要点：
- **日期先按 VARCHAR 导入**，避免 `2021/8/5` 这种非标准格式直接报错，导入后用 `STR_TO_DATE` 转换。
- 价格用 `DECIMAL(10,2)` 而非 FLOAT，避免浮点误差。

> 版本要求：本方案所有 SQL 基于 **MySQL 8.0+**（使用到窗口函数 `PERCENT_RANK` / `LAG` / `ROW_NUMBER`），执行前请用 `SELECT VERSION();` 确认。

---

## 4. Step 3｜数据导入（LOAD DATA）

```sql
LOAD DATA LOCAL INFILE 'C:/你的路径/淘宝用户行为.csv'
INTO TABLE t_raw
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
IGNORE 1 LINES
(invoice_no, customer_id, gender, age, category, quantity, price, payment_method, invoice_date);
```

导入后生成清洗宽表（一次性完成：转日期 + 计算订单金额 + 加主键）：
```sql
CREATE TABLE t_clean AS
SELECT invoice_no, customer_id, gender, age, category, quantity, price, payment_method,
       STR_TO_DATE(invoice_date,'%Y/%m/%d') AS inv_date,   -- 2021/8/5 对应 %Y/%m/%d
       quantity * price AS amount                          -- 单笔订单金额
FROM t_raw;

ALTER TABLE t_clean ADD PRIMARY KEY (invoice_no);
CREATE INDEX idx_cat ON t_clean(category);
CREATE INDEX idx_cust ON t_clean(customer_id);
```

> 踩坑提示：
> - 报 `can't connect local infile` → 客户端先执行 `SET GLOBAL local_infile = 1;`，或连接参数加 `--local-infile=1`
> - 中文乱码 → 连接与表都用 utf8mb4，LOAD DATA 加 `CHARACTER SET utf8mb4`
> - 导入行数对不上 → 检查 `LINES TERMINATED BY`。本数据实测为 CRLF：已按第 2 节预处理统一为 LF 时用 `'\n'`；若未预处理则改用 `'\r\n'`
> - 验证：`SELECT COUNT(*) FROM t_clean;` 应为 99,457

---

## 5. Step 4｜数据质量检查

```sql
-- ① 总量与唯一性
SELECT COUNT(*)                              AS 总记录,
       COUNT(DISTINCT customer_id)           AS 唯一客户,
       COUNT(DISTINCT invoice_no)            AS 唯一订单,
       COUNT(DISTINCT category)              AS 类目数;

-- ② 空值检查（期望全为 0）
SELECT SUM(customer_id IS NULL OR customer_id='') AS 缺客户,
       SUM(category IS NULL)                      AS 缺类目,
       SUM(amount IS NULL OR amount<0)            AS 负金额;

-- ③ 逻辑异常（期望 0）
SELECT COUNT(*) AS 数量异常 FROM t_clean WHERE quantity<=0 OR price<=0;

-- ④ 日期转换是否全部成功（期望 0）
SELECT COUNT(*) AS 日期转换失败 FROM t_raw WHERE STR_TO_DATE(invoice_date,'%Y/%m/%d') IS NULL;
```

---

## 6. Step 5｜描述性统计

```sql
-- 连续字段：金额、单价、数量、年龄
SELECT COUNT(*) 样本量,
       MIN(amount) 最小金额, MAX(amount) 最大金额,
       ROUND(AVG(amount),2) 平均金额,
       ROUND(STDDEV(amount),2) 金额标准差
FROM t_clean;

-- 分类字段频数
SELECT category, COUNT(*) 订单数, SUM(quantity) 销量, ROUND(SUM(amount),2) 销售额
FROM t_clean GROUP BY category ORDER BY 销售额 DESC;
```

---

## 7. Step 6｜六大主题分析（核心）

> 子节编号 `6.1~6.6` 与 SQL 脚本 `taobao_mysql_analysis.sql` 的分节编号**保持一致**（下列 SQL 均可直接对应脚本执行）。

### 6.1 全局经营概览
```sql
SELECT COUNT(*) 订单数, COUNT(DISTINCT customer_id) 客户数,
       ROUND(SUM(amount),2) 总销售额,
       ROUND(SUM(amount)/COUNT(*),2) 客单价(每单),
       ROUND(SUM(amount)/SUM(quantity),2) 平均件单价;
```

### 6.2 商品类目分析
- 类目销售额 / 销量 / 占比 TOP：
```sql
SELECT category 类目, COUNT(*) 订单数, SUM(quantity) 销量,
       ROUND(SUM(amount),2) 销售额,
       ROUND(SUM(amount)/SUM(SUM(amount)) OVER ()*100,2) 销售额占比
FROM t_clean GROUP BY category ORDER BY 销售额 DESC;
```
- 类目单价带（区分高价低频 / 低价高频）：
```sql
SELECT category 类目,
       ROUND(AVG(price),2) 平均单价, ROUND(AVG(amount),2) 平均订单额,
       ROUND(SUM(amount)/COUNT(*)/AVG(price),2) 平均件数
FROM t_clean GROUP BY category ORDER BY 平均单价 DESC;
```
- 类目 × 性别偏好（交叉表）：
```sql
SELECT category 类目,
       ROUND(SUM(gender='Female')/COUNT(*)*100,1) 女性占比,
       ROUND(SUM(gender='Male')/COUNT(*)*100,1)   男性占比,
       ROUND(SUM(amount),2) 销售额
FROM t_clean GROUP BY category ORDER BY 销售额 DESC;
```

### 6.3 用户画像分析
- 性别 / 年龄结构：
```sql
SELECT gender 性别, COUNT(*) 人数, ROUND(COUNT(*)/(SELECT COUNT(*) FROM t_clean)*100,1) 占比
FROM t_clean GROUP BY gender;

-- 年龄段分段（业务口径可自定义）
SELECT CASE WHEN age BETWEEN 18 AND 25 THEN '18-25'
            WHEN age BETWEEN 26 AND 35 THEN '26-35'
            WHEN age BETWEEN 36 AND 50 THEN '36-50'
            ELSE '50+' END 年龄段,
       COUNT(*) 人数, ROUND(AVG(amount),2) 平均消费
FROM t_clean GROUP BY 年龄段 ORDER BY 年龄段;
```
- 年龄段 × 类目偏好（各年龄段买最多的类目）：
```sql
SELECT 年龄段, 类目, 订单数, 销售额,
       ROW_NUMBER() OVER (PARTITION BY 年龄段 ORDER BY 销售额 DESC) rn
FROM (
  SELECT CASE WHEN age BETWEEN 18 AND 25 THEN '18-25'
              WHEN age BETWEEN 26 AND 35 THEN '26-35'
              WHEN age BETWEEN 36 AND 50 THEN '36-50'
              ELSE '50+' END 年龄段,
         category 类目, COUNT(*) 订单数, ROUND(SUM(amount),2) 销售额
  FROM t_clean GROUP BY 年龄段, 类目
) t HAVING rn <= 3;   -- 各年龄段 TOP3 类目
```

### 6.4 价格带分析
```sql
SELECT CASE WHEN amount < 100  THEN '0-100'
            WHEN amount < 300  THEN '100-300'
            WHEN amount < 600  THEN '300-600'
            WHEN amount < 1000 THEN '600-1000'
            ELSE '1000+' END 订单金额带,
       COUNT(*) 订单数,
       ROUND(COUNT(*)/SUM(COUNT(*)) OVER ()*100,1) 订单占比,
       ROUND(SUM(amount),2) 销售额
FROM t_clean GROUP BY 订单金额带 ORDER BY 订单数 DESC;
```

### 6.5 支付方式分析
```sql
SELECT payment_method 支付方式, COUNT(*) 订单数,
       ROUND(COUNT(*)/SUM(COUNT(*)) OVER ()*100,1) 占比,
       ROUND(AVG(amount),2) 平均订单额,
       ROUND(SUM(amount),2) 总销售额
FROM t_clean GROUP BY payment_method ORDER BY 订单数 DESC;

-- 支付方式 × 类目（高单价类目偏好哪种支付）
SELECT category 类目, payment_method 支付方式, COUNT(*) 订单数
FROM t_clean GROUP BY category, payment_method ORDER BY category, 订单数 DESC;
```

### 6.6 时间趋势分析
- 月度销售趋势：
```sql
SELECT DATE_FORMAT(inv_date,'%Y-%m') 月份,
       COUNT(*) 订单数, ROUND(SUM(amount),2) 销售额
FROM t_clean GROUP BY 月份 ORDER BY 月份;
```
- 月度环比增长率（窗口函数）：
```sql
SELECT 月份, 销售额, 环比增长率 FROM (
  SELECT DATE_FORMAT(inv_date,'%Y-%m') 月份,
         ROUND(SUM(amount),2) 销售额,
         ROUND((SUM(amount)-LAG(SUM(amount)) OVER (ORDER BY DATE_FORMAT(inv_date,'%Y-%m')))
               /LAG(SUM(amount)) OVER (ORDER BY DATE_FORMAT(inv_date,'%Y-%m'))*100,1) 环比增长率
  FROM t_clean GROUP BY 月份
) t ORDER BY 月份;
```
- 星期几消费分布（周末效应）：
```sql
SELECT DAYNAME(inv_date) 星期, COUNT(*) 订单数
FROM t_clean GROUP BY 星期 ORDER BY FIELD(DAYNAME(inv_date),'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday');
```
> 注：2023 年仅到 3 月 8 日，做同比时注意 2023 年数据不完整。

---

## 8. Step 7｜客户分群与进阶建模

> 子节编号 `7.1~7.4` 与 SQL 脚本分节一致（对应脚本 STEP 7 的 7.1~7.3）。

由于每用户仅一笔交易，**RFM 退化为"单笔消费价值"分层**，聚类改用**人口属性 + 单次消费特征**。

### 7.1 单笔消费价值分层（SQL 分位法）
```sql
CREATE TABLE cust_segment AS
SELECT customer_id, gender, age, category, payment_method, amount, inv_date,
       CASE WHEN pct >= 0.80 THEN '高价值'
            WHEN pct >= 0.50 THEN '中价值'
            ELSE '低价值' END 客户分层
FROM (
  SELECT customer_id, gender, age, category, payment_method, amount, inv_date,
         PERCENT_RANK() OVER (ORDER BY amount) AS pct
  FROM t_clean
) t;

SELECT 客户分层, COUNT(*) 人数, ROUND(SUM(amount),2) 销售额,
       ROUND(SUM(amount)/SUM(SUM(amount)) OVER ()*100,1) 销售额贡献占比
FROM cust_segment GROUP BY 客户分层;
```

### 7.2 类目偏好特征宽表（供聚类使用）
每用户一行，维度 = 人口属性 + 是否购买某类目 + 金额 + 数量：
```sql
CREATE TABLE user_features AS
SELECT c.customer_id, c.gender, c.age, c.payment_method, c.amount, c.quantity,
       c.category AS main_category,
       CASE WHEN c.category='Technology' THEN 1 ELSE 0 END AS buy_tech,
       CASE WHEN c.category='Clothing'   THEN 1 ELSE 0 END AS buy_clothing,
       CASE WHEN c.category='Cosmetics'  THEN 1 ELSE 0 END AS buy_cosmetics,
       CASE WHEN c.category='Food & Beverage' THEN 1 ELSE 0 END AS buy_food,
       CASE WHEN c.category='Toys'       THEN 1 ELSE 0 END AS buy_toys,
       CASE WHEN c.category='Shoes'      THEN 1 ELSE 0 END AS buy_shoes,
       CASE WHEN c.category='Books'      THEN 1 ELSE 0 END AS buy_books,
       CASE WHEN c.category='Souvenir'   THEN 1 ELSE 0 END AS buy_souvenir
FROM t_clean c;
-- 导出：SELECT ... INTO OUTFILE 或客户端导出为 CSV，交给 Python 做 KMeans
```

### 7.3 导出到 Python 做 KMeans 聚类（进阶）
1. MySQL 导出 `user_features` 为 CSV（用 mysql client 或 Workbench/DBeaver）。
2. Python 参考（`uv run --with pandas --with scikit-learn python`）：

```python
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

df = pd.read_csv("user_features.csv")
feat = ["age","amount","quantity","buy_tech","buy_clothing","buy_cosmetics",
        "buy_food","buy_toys","buy_shoes","buy_books","buy_souvenir"]
X = StandardScaler().fit_transform(df[feat].fillna(0))

model = KMeans(n_clusters=4, n_init=10, random_state=42)
df["cluster"] = model.fit_predict(X)
# 输出每个簇画像：年龄均值、金额均值、主导类目、支付方式
print(df.groupby("cluster")[["age","amount"]].mean())
```

### 7.4 可进一步做的（可选）
- **类目 × 年龄 × 性别 三维画像**：直接交叉聚合，画热力图。
- **支付方式与客单价的因果性观察**：高客单是否更倾向用 Card/Alipay。
- **2021 vs 2022 年度类目结构变化**：类目占比的同比漂移。

---

## 9. 可视化建议

MySQL 出数后，推荐工具：**Power BI / Tableau / Superset**，或 Python Matplotlib / ECharts。

| 分析主题 | 推荐图表 |
|---|---|
| 类目销售额占比 | 柱状图 + 环形图 |
| 类目 × 性别偏好 | 分组柱状图 / 热力图 |
| 价格带分布 | 直方图 / 漏斗图 |
| 月度趋势 + 环比 | 折线图 + 标注增长率 |
| 支付方式结构 | 饼图 / 堆叠柱状图 |
| 客户分层贡献 | Pareto（二八法则）图 |
| 聚类结果 | 雷达图（每簇特征）|

---

## 10. 分层运营策略｜如何让每一类用户花得更多

> 这是对 STEP 7 客户分层的**业务延伸**：分层不是终点，把"分层结果"转化为"运营动作"才是。目标一句话——**对每一类用户，找到最有效的"提值"抓手**。

### 10.1 提值的三条业务路径

用户消费金额 = 单次金额 × 购买频次 × 购买品类数。提升花费只有三条路：

| 路径 | 机制 | 典型抓手 | 本数据能否直接支撑 |
|---|---|---|---|
| 提客单 | 单次买得更贵 / 更多 | 满减、捆绑、向上销售 | ✅ 可（价格带、客单分析） |
| 提频 | 买得更勤 | 复购券、会员订阅 | ⚠️ 需行为序列数据回流 |
| 扩品类 | 买更多品类 | 交叉推荐、组合套餐 | ⚠️ 数据限单类目，用人群画像重叠近似 |

### 10.2 分层策略矩阵（核心交付）

| 用户群 | 数据画像 | 核心问题 | 运营抓手（具体动作） |
|---|---|---|---|
| **高价值**（前20%） | 大额类目（Technology/大件）、成熟客 | 客单触顶、流失损失大 | VIP 等级 / 专属客服 / 新品首发权；向上销售高级 SKU；大额满减（门槛设在其价格带上沿） |
| **中价值**（中间50%） | 单类目、消费力未被释放 | 品类单一、潜力未激发 | 交叉销售（按其主类目推荐画像相邻类目）；组合套餐；会员积分累计 |
| **低价值**（后30%） | 低价类目（Food/Souvenir/Books）、偏年轻 | 客单过低、易流失 | 首单优惠 + 满额包邮提首单客单；升级推荐（低价带→中价带）；二次购买券养复购 |

### 10.3 交叉画像的差异化动作（年龄 × 性别 × 价值）

- **18-25 年轻低价值**：潮品/新品上新、社交裂变、低价尝鲜盒 → 先"提频 + 扩品类"
- **26-35 职场中价值**：品质升级、套装组合、大件分期 → 主打"提客单"
- **50+ 高价值成熟客**：会员制、一对一服务、信任型内容 → 主"留量 + 向上销售"

### 10.4 运营抓手 → 数据支撑（每个动作都有 SQL 依据）

| 运营抓手 | 数据依据 | 对应 SQL |
|---|---|---|
| 满减门槛设在哪 | 价格带断层（峰值→空隙） | 6.4 价格带、7.3.4 类目价格结构 |
| 交叉销售推什么 | 类目×人群偏好、类目平均客单 | 6.3、6.2、7.3.1 |
| 向上销售推什么 | 类目内价格分布与离散度 | 7.3.4 |
| 权益发给谁 | 消费价值分层 + 分层画像 | STEP 7、7.3.1~7.3.3 |
| 支付渠道满减 | 支付×客单、分层支付偏好 | 6.5、7.3.3 |

### 10.5 效果验证闭环

策略上线后持续回流数据验证四个指标：**客单价、复购率、高价值客户占比、类目渗透率**，运营前后对比或 A/B 测试。
> **边界说明**：本数据集是"一次性交易快照"，提频/复购类指标无法在现有数据上直接验证，需平台侧持续采集新交易数据后才有依据。

---

## 11. 结论与建议

1. **数据定位**：这是"订单级交易明细"而非"行为序列日志"，据此调整分析口径，避免误用 RFM / 漏斗 / 关联规则。
2. **最有价值的三个方向**：① 类目 × 人群交叉偏好；② 单笔消费价值分层（高价值客群特征）；③ 月度趋势与周期。
3. **若要真正做"行为路径挖掘"**，需换用带 `behavior_type`（pv/fav/cart/buy）且同一用户多次行为的序列数据（如阿里天池 UserBehavior），届时本方案中的 RFM、复购、漏斗、关联规则才能落地。
