# 数据来源与复现

核查日期：2026-11-10。

## 租房历史数据

采用 [UCI Apartment for Rent Classified](https://archive.ics.uci.edu/dataset/555/apartment%2Bfor%2Brent%2Bclassified)，数据集引用：Apartment for Rent Classified [Dataset]. (2019). UCI Machine Learning Repository. https://doi.org/10.24432/C5X623 。官方页面标注 CC BY 4.0，要求适当署名。

下载的 10K 版本有 10,000 条记录，其中芝加哥 148 条，均为 USD 月度租金；导入记录时间范围为 2019-12-02 至 2019-12-26。它们是历史广告，不含已验证的住客体验、完整月度费用或当前可租状态。

转换保留房源正文、原始发布来源、原字段和日期。`pets_allowed` 的 None/null 不解释为禁止宠物；`fee=No` 不解释为没有任何水电或停车等月费。所有候选总月费完整性均设为未知。原始文件与转换数据保存在被 Git 忽略的 data/private 下。

原始 CSV SHA-256：`522df3a6170cdd83adf6ba1fe5a0c9143fbdb23bc36d671fbd870916727202fd`。

在项目目录复现（解压使用支持 7z 的 bsdtar）：

```sh
mkdir -p data/private/uci
curl -fL --max-time 60 'https://archive.ics.uci.edu/static/public/555/apartment%2Bfor%2Brent%2Bclassified.zip' -o data/private/uci/source.zip
bsdtar -xf data/private/uci/source.zip -C data/private/uci apartments_for_rent_classified_10K.7z
bsdtar -xf data/private/uci/apartments_for_rent_classified_10K.7z -C data/private/uci
python3 import_uci.py data/private/uci/apartments_for_rent_classified_10K.csv
python3 cli.py search --data data/private/chicago.json --topic parking
```

## 第二场景候选来源

[Inside Airbnb](https://insideairbnb.com/get-the-data/) 提供详细房源及评论数据，并标注公开下载数据为 CC BY 4.0。后续住宿场景将验证具体文件的字段、日期及引用要求；本轮尚未下载或导入。短期住宿评论不能混入长期租房候选。

## 模型接口依据

根据 [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) 使用 Responses API 的 text.format JSON Schema，并处理拒绝和未完成状态。结构符合 schema 不保证语义正确；本地继续检查引文及来源关系，语义支持仍需人工或独立评估。
