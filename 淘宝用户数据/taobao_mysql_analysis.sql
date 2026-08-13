-- ============================================================================
-- 电商交易数据 MySQL 分析脚本
-- 配套文档：淘宝用户行为_MySQL分析方案.md
-- 环境要求：MySQL 8.0+（窗口函数 PERCENT_RANK / LAG / ROW_NUMBER 需 8.0）
--
-- 前置准备（在 shell / cmd 中执行）：
--   1) 预处理 CSV（实测为 CRLF 行尾，且每行尾带 ,,,,,）：
--        同时去除 \r（CRLF->LF）并清理行尾空逗号：
--        sed -i 's/\r$//; s/,*$//' "淘宝用户行为.csv"
--      （或用编辑器：正则 ,+$ 替换为空，并把 EOL 统一为 LF）
--   2) 启动 mysql 时允许本地导入（任选其一）：
--        SET GLOBAL local_infile = 1;
--        或连接参数：mysql --local-infile=1 -u root -p
--   3) 把下方 LOAD DATA 路径换成实际文件路径
-- ============================================================================


-- ----------------------------------------------------------------------------
-- STEP 1  建库建表
-- ----------------------------------------------------------------------------
CREATE DATABASE IF NOT EXISTS taobao_analysis DEFAULT CHARSET utf8mb4;
USE taobao_analysis;

DROP TABLE IF EXISTS t_raw;
CREATE TABLE t_raw (
  invoice_no     VARCHAR(20)     COMMENT '订单号',
  customer_id    VARCHAR(20)     COMMENT '客户ID',
  gender         VARCHAR(10)     COMMENT '性别',
  age            INT             COMMENT '年龄',
  category       VARCHAR(30)     COMMENT '商品类目',
  quantity       INT             COMMENT '数量',
  price          DECIMAL(10,2)   COMMENT '单价',
  payment_method VARCHAR(20)     COMMENT '支付方式',
  invoice_date   VARCHAR(10)     COMMENT '发票日期(字符串)'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='原始交易明细';


-- ----------------------------------------------------------------------------
-- STEP 2  导入数据（路径请自行替换；若乱码检查 CHARACTER SET）
-- ----------------------------------------------------------------------------
LOAD DATA LOCAL INFILE 'C:/你的路径/淘宝用户行为.csv'
INTO TABLE t_raw
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'          -- 本数据为 CRLF；已按前置预处理统一为 LF 则用 '\n'，否则改用 '\r\n'
IGNORE 1 LINES
(invoice_no, customer_id, gender, age, category, quantity, price, payment_method, invoice_date);


-- ----------------------------------------------------------------------------
-- STEP 3  清洗宽表：转日期 + 算订单金额 + 主键/索引
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS t_clean;
CREATE TABLE t_clean AS
SELECT invoice_no,
       customer_id,
       gender,
       age,
       category,
       quantity,
       price,
       payment_method,
       STR_TO_DATE(invoice_date, '%Y/%m/%d') AS inv_date,   -- 2021/8/5 -> DATE
       quantity * price                      AS amount       -- 单笔订单金额
FROM t_raw;

ALTER TABLE t_clean ADD PRIMARY KEY (invoice_no);
CREATE INDEX idx_cat  ON t_clean(category);
CREATE INDEX idx_cust ON t_clean(customer_id);


-- ----------------------------------------------------------------------------
-- STEP 4  数据质量检查（期望值已注明）
-- ----------------------------------------------------------------------------
-- ① 总量：应 99,457 行；唯一客户/订单均 99,457
SELECT COUNT(*)                          AS 总记录,
       COUNT(DISTINCT customer_id)       AS 唯一客户,
       COUNT(DISTINCT invoice_no)        AS 唯一订单,
       COUNT(DISTINCT category)          AS 类目数
FROM t_clean;

-- ② 空值（期望 0）
SELECT SUM(customer_id IS NULL OR customer_id = '') AS 缺客户,
       SUM(category   IS NULL)                     AS 缺类目,
       SUM(inv_date   IS NULL)                     AS 日期转换失败
FROM t_clean;

-- ③ 逻辑异常（期望 0）
SELECT COUNT(*) AS 数量或金额异常
FROM t_clean
WHERE quantity <= 0 OR price <= 0 OR amount <= 0;

-- ④ 年龄范围
SELECT MIN(age) 最小年龄, MAX(age) 最大年龄, ROUND(AVG(age),1) 平均年龄 FROM t_clean;


-- ----------------------------------------------------------------------------
-- STEP 5  描述性统计
-- ----------------------------------------------------------------------------
SELECT COUNT(*)                         AS 样本量,
       ROUND(MIN(amount),2)             AS 最小订单额,
       ROUND(MAX(amount),2)             AS 最大订单额,
       ROUND(AVG(amount),2)             AS 平均订单额,
       ROUND(STDDEV(amount),2)          AS 订单额标准差,
       ROUND(AVG(quantity),2)           AS 平均件数
FROM t_clean;


-- ============================================================================
-- STEP 6  主题分析
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 6.1 全局经营概览
-- ----------------------------------------------------------------------------
SELECT COUNT(*)                          AS 订单数,
       COUNT(DISTINCT customer_id)       AS 客户数,
       ROUND(SUM(amount),2)              AS 总销售额,
       ROUND(SUM(amount)/COUNT(*),2)     AS 每单客单价,
       ROUND(SUM(amount)/SUM(quantity),2) AS 平均件单价
FROM t_clean;

-- ----------------------------------------------------------------------------
-- 6.2 商品类目分析
-- ----------------------------------------------------------------------------
-- 6.2.1 类目销售额 / 销量 / 占比
SELECT category                                      AS 类目,
       COUNT(*)                                      AS 订单数,
       SUM(quantity)                                 AS 销量,
       ROUND(SUM(amount),2)                          AS 销售额,
       ROUND(SUM(amount) / SUM(SUM(amount)) OVER () * 100, 2) AS 销售额占比
FROM t_clean
GROUP BY category
ORDER BY 销售额 DESC;

-- 6.2.2 类目价格结构（高单价 vs 高频）
SELECT category                     AS 类目,
       ROUND(AVG(price),2)          AS 平均单价,
       ROUND(AVG(amount),2)         AS 平均订单额,
       ROUND(SUM(quantity)/COUNT(*),2) AS 平均件数
FROM t_clean
GROUP BY category
ORDER BY 平均单价 DESC;

-- 6.2.3 类目 × 性别 偏好交叉
SELECT category                               AS 类目,
       ROUND(SUM(gender='Female')/COUNT(*)*100,1) AS 女性占比,
       ROUND(SUM(gender='Male')/COUNT(*)*100,1)   AS 男性占比,
       ROUND(SUM(amount),2)                       AS 销售额
FROM t_clean
GROUP BY category
ORDER BY 销售额 DESC;

-- ----------------------------------------------------------------------------
-- 6.3 用户画像分析
-- ----------------------------------------------------------------------------
-- 6.3.1 性别结构
SELECT gender                     AS 性别,
       COUNT(*)                   AS 人数,
       ROUND(COUNT(*) / (SELECT COUNT(*) FROM t_clean) * 100, 1) AS 占比
FROM t_clean
GROUP BY gender;

-- 6.3.2 年龄段结构 + 平均消费
SELECT CASE WHEN age BETWEEN 18 AND 25 THEN '18-25'
            WHEN age BETWEEN 26 AND 35 THEN '26-35'
            WHEN age BETWEEN 36 AND 50 THEN '36-50'
            ELSE '50+' END            AS 年龄段,
       COUNT(*)                        AS 人数,
       ROUND(AVG(amount),2)            AS 平均消费
FROM t_clean
GROUP BY 年龄段
ORDER BY 年龄段;

-- 6.3.3 各年龄段消费 TOP3 类目
SELECT 年龄段, 类目, 订单数, 销售额
FROM (
  SELECT CASE WHEN age BETWEEN 18 AND 25 THEN '18-25'
              WHEN age BETWEEN 26 AND 35 THEN '26-35'
              WHEN age BETWEEN 36 AND 50 THEN '36-50'
              ELSE '50+' END                     AS 年龄段,
         category                                 AS 类目,
         COUNT(*)                                 AS 订单数,
         ROUND(SUM(amount),2)                     AS 销售额,
         ROW_NUMBER() OVER (PARTITION BY
            CASE WHEN age BETWEEN 18 AND 25 THEN '18-25'
                 WHEN age BETWEEN 26 AND 35 THEN '26-35'
                 WHEN age BETWEEN 36 AND 50 THEN '36-50'
                 ELSE '50+' END
            ORDER BY SUM(amount) DESC)            AS rn
  FROM t_clean
  GROUP BY 年龄段, 类目
) t
WHERE rn <= 3;

-- ----------------------------------------------------------------------------
-- 6.4 价格带分析
-- ----------------------------------------------------------------------------
SELECT CASE WHEN amount < 100  THEN '0-100'
            WHEN amount < 300  THEN '100-300'
            WHEN amount < 600  THEN '300-600'
            WHEN amount < 1000 THEN '600-1000'
            ELSE '1000+' END                    AS 订单金额带,
       COUNT(*)                                  AS 订单数,
       ROUND(COUNT(*) / SUM(COUNT(*)) OVER () * 100, 1) AS 订单占比,
       ROUND(SUM(amount),2)                      AS 销售额
FROM t_clean
GROUP BY 订单金额带
ORDER BY 订单数 DESC;

-- ----------------------------------------------------------------------------
-- 6.5 支付方式分析
-- ----------------------------------------------------------------------------
SELECT payment_method                                      AS 支付方式,
       COUNT(*)                                            AS 订单数,
       ROUND(COUNT(*) / SUM(COUNT(*)) OVER () * 100, 1)    AS 占比,
       ROUND(AVG(amount),2)                                AS 平均订单额,
       ROUND(SUM(amount),2)                                AS 总销售额
FROM t_clean
GROUP BY payment_method
ORDER BY 订单数 DESC;

-- 支付方式 × 类目（高单价类目偏好哪种支付）
SELECT category AS 类目, payment_method AS 支付方式, COUNT(*) AS 订单数
FROM t_clean
GROUP BY category, payment_method
ORDER BY category, 订单数 DESC;

-- ----------------------------------------------------------------------------
-- 6.6 时间趋势分析
-- ----------------------------------------------------------------------------
-- 6.6.1 月度销售趋势
SELECT DATE_FORMAT(inv_date, '%Y-%m') AS 月份,
       COUNT(*)                        AS 订单数,
       ROUND(SUM(amount),2)            AS 销售额
FROM t_clean
GROUP BY 月份
ORDER BY 月份;

-- 6.6.2 月度环比增长率
SELECT 月份, 销售额, 环比增长率
FROM (
  SELECT DATE_FORMAT(inv_date, '%Y-%m')                                        AS 月份,
         ROUND(SUM(amount),2)                                                  AS 销售额,
         ROUND((SUM(amount) - LAG(SUM(amount)) OVER (ORDER BY DATE_FORMAT(inv_date,'%Y-%m')))
               / LAG(SUM(amount)) OVER (ORDER BY DATE_FORMAT(inv_date,'%Y-%m')) * 100, 1) AS 环比增长率
  FROM t_clean
  GROUP BY 月份
) t
ORDER BY 月份;

-- 6.6.3 星期几消费分布（周末效应）
SELECT DAYNAME(inv_date) AS 星期, COUNT(*) AS 订单数
FROM t_clean
GROUP BY 星期
ORDER BY FIELD(DAYNAME(inv_date),
       'Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday');

-- 6.6.4 年度概览（注意 2023 年仅到 3 月，同比需谨慎）
SELECT YEAR(inv_date) AS 年份,
       COUNT(*)       AS 订单数,
       ROUND(SUM(amount),2) AS 销售额,
       COUNT(DISTINCT customer_id) AS 客户数
FROM t_clean
GROUP BY 年份
ORDER BY 年份;


-- ============================================================================
-- STEP 7  客户分群与进阶建模
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 7.1 单笔消费价值分层（分位法：前20%高价值 / 中50% / 低30%）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS cust_segment;
CREATE TABLE cust_segment AS
SELECT customer_id, gender, age, category, payment_method, amount, inv_date,
       CASE WHEN pct >= 0.80 THEN '高价值'
            WHEN pct >= 0.50 THEN '中价值'
            ELSE '低价值' END AS 客户分层
FROM (
  SELECT customer_id, gender, age, category, payment_method, amount, inv_date,
         PERCENT_RANK() OVER (ORDER BY amount) AS pct
  FROM t_clean
) t;

-- 各分层人数与销售额贡献（验证二八法则）
SELECT 客户分层,
       COUNT(*)                                AS 人数,
       ROUND(SUM(amount),2)                    AS 销售额,
       ROUND(SUM(amount) / SUM(SUM(amount)) OVER () * 100, 1) AS 销售额贡献占比
FROM cust_segment
GROUP BY 客户分层;

-- 高价值客群画像：性别 / 年龄 / 类目 / 支付
SELECT gender      AS 性别, COUNT(*) AS 人数 FROM cust_segment WHERE 客户分层='高价值' GROUP BY 性别;
SELECT category    AS 类目, COUNT(*) AS 人数 FROM cust_segment WHERE 客户分层='高价值' GROUP BY category ORDER BY 人数 DESC;
SELECT payment_method AS 支付方式, COUNT(*) AS 人数 FROM cust_segment WHERE 客户分层='高价值' GROUP BY payment_method ORDER BY 人数 DESC;

-- ----------------------------------------------------------------------------
-- 7.2 类目偏好特征宽表（用户一行，供 Python KMeans 聚类）
--    导出命令示例（命令行）：
--      mysql -u root -p taobao_analysis -e "SELECT * FROM user_features" -B > user_features.tsv
--    或使用 DBeaver / Workbench 导出 CSV。
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS user_features;
CREATE TABLE user_features AS
SELECT customer_id,
       gender,
       age,
       payment_method,
       category                  AS main_category,
       quantity,
       price,
       amount,
       CASE WHEN category='Technology'     THEN 1 ELSE 0 END AS buy_tech,
       CASE WHEN category='Clothing'       THEN 1 ELSE 0 END AS buy_clothing,
       CASE WHEN category='Cosmetics'      THEN 1 ELSE 0 END AS buy_cosmetics,
       CASE WHEN category='Food & Beverage' THEN 1 ELSE 0 END AS buy_food,
       CASE WHEN category='Toys'           THEN 1 ELSE 0 END AS buy_toys,
       CASE WHEN category='Shoes'          THEN 1 ELSE 0 END AS buy_shoes,
       CASE WHEN category='Books'          THEN 1 ELSE 0 END AS buy_books,
       CASE WHEN category='Souvenir'       THEN 1 ELSE 0 END AS buy_souvenir
FROM t_clean;

-- 验证特征表规模（应与总行数一致）
SELECT COUNT(*) 特征行数 FROM user_features;

-- 每个类目对平均客单价的贡献（供聚类解释）
SELECT main_category AS 类目,
       COUNT(*)      AS 人数,
       ROUND(AVG(amount),2) AS 平均消费
FROM user_features
GROUP BY 类目
ORDER BY 平均消费 DESC;


-- ----------------------------------------------------------------------------
-- STEP 7.3  分层运营画像
-- 目的：为"让每一类用户花得更多"（分层运营策略）提供决策依据
-- ----------------------------------------------------------------------------
-- 7.3.1 各价值分层的主导类目与平均订单额
SELECT 客户分层, category AS 类目,
       COUNT(*)                AS 人数,
       ROUND(AVG(amount),2)    AS 平均订单额
FROM cust_segment
GROUP BY 客户分层, 类目
ORDER BY 客户分层, 平均订单额 DESC;

-- 7.3.2 各价值分层的年龄段分布
SELECT 客户分层,
       CASE WHEN age BETWEEN 18 AND 25 THEN '18-25'
            WHEN age BETWEEN 26 AND 35 THEN '26-35'
            WHEN age BETWEEN 36 AND 50 THEN '36-50'
            ELSE '50+' END       AS 年龄段,
       COUNT(*)                  AS 人数
FROM cust_segment
GROUP BY 客户分层, 年龄段
ORDER BY 客户分层, 人数 DESC;

-- 7.3.3 各价值分层的支付偏好（指导"哪个支付渠道放满减"）
SELECT 客户分层, payment_method AS 支付方式,
       COUNT(*) AS 人数
FROM cust_segment
GROUP BY 客户分层, 支付方式
ORDER BY 客户分层, 人数 DESC;

-- 7.3.4 类目价格结构（为向上销售 / 满减门槛找价格带与断层）
SELECT category                    AS 类目,
       ROUND(MIN(price),2)         AS 最低单价,
       ROUND(MAX(price),2)         AS 最高单价,
       ROUND(AVG(price),2)         AS 平均单价,
       ROUND(STDDEV(price),2)      AS 单价离散度,
       ROUND(AVG(amount),2)        AS 平均订单额
FROM t_clean
GROUP BY category
ORDER BY 平均单价 DESC;


-- ----------------------------------------------------------------------------
-- STEP 8  最终经营 KPI 汇总（一键输出关键指标）
-- ----------------------------------------------------------------------------
SELECT '订单数'     AS 指标, COUNT(*)                        AS 数值 FROM t_clean
UNION ALL SELECT '客户数',   COUNT(DISTINCT customer_id)             FROM t_clean
UNION ALL SELECT '总销售额', ROUND(SUM(amount),2)                    FROM t_clean
UNION ALL SELECT '客单价',   ROUND(SUM(amount)/COUNT(*),2)           FROM t_clean
UNION ALL SELECT '平均件数', ROUND(SUM(quantity)/COUNT(*),2)         FROM t_clean;
