# Test Asset 数据集下载指南

本目录包含三个用于验证 Schema Profiler 的测试数据集。由于 Kaggle 需要登录认证，请按以下步骤手动下载并放入对应文件夹。

---

## 1. Olist Brazilian E-Commerce（经典星型模型与语义测试）

**目标路径**：`test_asset/olist_brazilian_ecommerce/`

**Kaggle 页面**：https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

**需下载的 9 张 CSV**：
```
olist_customers_dataset.csv
olist_geolocation_dataset.csv
olist_order_items_dataset.csv
olist_order_payments_dataset.csv
olist_order_reviews_dataset.csv
olist_orders_dataset.csv
olist_products_dataset.csv
olist_sellers_dataset.csv
product_category_name_translation.csv
```

**测试重点**：
- 规范的主外键结构（order_id, customer_id, product_id, seller_id）
- olist_geolocation_dataset.csv 包含邮编+经纬度，验证 SemanticTyper 地理位置识别
- 多个时间戳字段，验证时间语义理解
- 星型模型，适合多表 join 和主外键召回测试

---

## 2. Instacart Market Basket Analysis（极限抗压与采样测试）

**目标路径**：`test_asset/instacart_market_basket/`

**Kaggle 页面**：https://www.kaggle.com/c/instacart-market-basket-analysis/data

**需下载的 6 张核心 CSV**：
```
aisles.csv
departments.csv
orders.csv
products.csv
order_products__prior.csv      # 3000万+行，约500MB+
order_products__train.csv
```

**测试重点**：
- order_products__prior.csv 是天然内存/性能压测素材
- 验证 >500MB → 仅2千行的轻量化拦截逻辑
- 验证 MinHash/LSH 在极高基数下的分桶速度

---

## 3. Home Credit Default Risk（复杂特征与混淆列名测试）

**目标路径**：`test_asset/home_credit_default_risk/`

**Kaggle 页面**：https://www.kaggle.com/c/home-credit-default-risk

**需下载的 7 张核心 CSV**：
```
application_train.csv
application_test.csv
bureau.csv
bureau_balance.csv
credit_card_balance.csv
installments_payments.csv
POS_CASH_balance.csv
previous_application.csv
```

**测试重点**：
- 单表可达 100+ 列，大量同名/相近数值字段（AMT_, DAYS_, CNT_ 前缀）
- 验证统计分布相似度（均值/标准差发现相似信用指标）
- 验证 ColumnEmbedder 字符级 TF-IDF 在非标准命名列上的语义提取

---

## 快速下载命令（需先配置 Kaggle API）

```bash
# 1. 安装 Kaggle CLI
pip install kaggle

# 2. 在 Kaggle 账户页面生成 API Token，下载 kaggle.json
#    放置到 ~/.kaggle/kaggle.json

# 3. 下载数据集
kaggle datasets download -d olistbr/brazilian-ecommerce -p test_asset/olist_brazilian_ecommerce/ --unzip
kaggle competitions download -c instacart-market-basket-analysis -p test_asset/instacart_market_basket/ --unzip
kaggle competitions download -c home-credit-default-risk -p test_asset/home_credit_default_risk/ --unzip
```

**注意**： competitions 数据需要先在 Kaggle 页面上接受竞赛规则才能下载。
