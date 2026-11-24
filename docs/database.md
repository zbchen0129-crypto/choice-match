# PostgreSQL 与混合检索

本地已建立 PostgreSQL 18 和 pgvector 数据库，使用项目专属目录 `data/private/postgres`、端口 `127.0.0.1:55437` 和 SCRAM 密码认证。未注册开机服务。数据库连接信息自动追加到被 Git 忽略的 `.env`，原有模型密钥保留。

## 日常启动

在项目目录运行：

```sh
.venv/bin/python local_db.py start
python3 server.py
```

打开 http://127.0.0.1:8767 。server.py 在配置了数据库时自动使用项目虚拟环境。数据库关闭时明确报错，不会悄悄退回 JSON。

`local_db.py stop` 停止项目数据库；数据文件保留。`local_db.py status` 检查进程。此脚本使用 Apple Silicon Homebrew 的 PostgreSQL 18 路径；其他机器可使用标准 PostgreSQL 实例并填写 DATABASE_URL，运行迁移。当前用户为隔离开发实例的管理角色，尚未设计生产权限及备份策略。

## 可复现初始化

本机已完成以下步骤，无需重复安装：

```sh
brew install postgresql@18 pgvector
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python local_db.py init
.venv/bin/python local_db.py start
.venv/bin/python db_manage.py migrate
.venv/bin/python db_manage.py import
.venv/bin/python db_manage.py embed
```

embed 会将来源文本发送到 OpenAI 并产生 Embedding API 用量；当前使用 text-embedding-3-small、1536 维。重复运行只处理缺失或模型不一致的向量。单条文本按字符边界切成不超过 1200 字符的片段，重叠 150 字符，保留精确起止位置。

## 数据结构

| 表 | 用途 |
|---|---|
| candidates | 候选身份、所属数据集、类型、演示或历史标记、原始候选快照 |
| rental_details | SQL 筛选使用的卧室、养猫规则、月费下界和完整性 |
| sources | 原文、来源日期、元数据和内容哈希 |
| chunks | 原文片段、位置、全文检索字段、Embedding 和模型名 |
| evidence | 正负证据、引文、条件、源哈希与抽取版本 |
| import_runs | 导入时间、输入哈希、记录数 |
| query_embeddings | 主题查询向量缓存，按模型和查询内容区分 |
| schema_migrations | 已执行迁移及校验和 |

导入是事务内 upsert，重复导入不新增候选或片段；保留独立导入审计记录。来源内容改变会在同一事务内使旧片段、向量及相关证据失效。来源删除会级联删除其片段和证据。导入不会自动删除此次未出现的整个房源，后续需要显式定义快照撤销策略。

候选快照用于还原现有界面的数据契约；标准化租房列用于 SQL 硬条件筛选。SQL 与应用筛选结果必须一致，否则停止推荐。未知字段保留在待核实集合。模型抽取结果按来源哈希和版本持久化，但本轮尚未实现抽取结果缓存复用，重复 AI 分析仍会调用生成模型。

## 混合检索流程

从数据库加载候选并执行 SQL 条件筛选。对通过或未知的全部候选，分别进行英文全文检索（补充中文关键词匹配）和向量余弦距离检索，各取最多 40 个片段，使用 RRF 合并。

按主题覆盖与加权检索分形成最多 5 个候选的短名单。同一候选在同一主题只取最高相关片段分，减少评论数量造成的偏差。对每个入选候选再检索上下文，模型读取对应完整来源，保留正反证据。最终推荐排序依据证据方向，不直接使用向量相似度作为适合程度。

当前采用精确向量扫描，尚未建立 HNSW 等近似索引；在 158 个片段的规模下避免引入近似召回误差。主题查询使用固定双语关键词和英文语义描述，尚未将所有用户细粒度偏好转成动态检索查询。语义检索总会返回最接近的文本，命中不代表该文本真正支持主题，仍由抽取和评估处理。

## 验证记录

2026-11-11：152 个候选（148 条历史广告、4 条虚构样例）、158 条来源、158 个片段全部持久化。首次向量生成使用 9,114 个输入 token；重复导入后再次生成处理 0 个片段、使用 0 个 token。

数据库实际停止后重新启动，152 个候选及 158 个向量全部保留。43 项测试通过，包括 5 项真实 PostgreSQL 集成测试：持久化往返、未知硬条件、重复导入与向量失效、失败事务回滚、混合检索的候选隔离。

真实模型验证通过数据库读取和混合检索生成了 5 条虚构案例解释；A、D 为已知满足，C 为待核实，B 被排除。历史数据先筛出 69 个通过或待核实候选，再基于混合检索形成 5 个短名单，已不再简单取 ID 排序的前 5 个。短名单质量尚需独立标注评估，不能据此声称效果提升。

```sh
# 普通测试，数据库测试默认跳过
.venv/bin/python -m unittest discover -s tests -v
# 数据库测试需要先在运行进程中加载 .env 并设置 CHOICEMATCH_DB_TEST=1
# 真实模型冒烟会产生 API 用量
.venv/bin/python verify_database.py
```

实现依据：[pgvector](https://github.com/pgvector/pgvector)、[Psycopg 安装文档](https://www.psycopg.org/psycopg3/docs/basic/install.html)、[OpenAI Embeddings API](https://developers.openai.com/api/reference/resources/embeddings/methods/create)。
