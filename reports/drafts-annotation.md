# drafts_50 等级标注（首轮）

- 标注人：实现者（规则初筛，`annotator=implementer-rule-pass-1`），**不是业务方复核**
- 样本：50 条；分布：A=30、B=15、C=5
- A 档占比（仅作初筛参考）：60.00%

| case_id | 意图 | 参考档 | 实测档 | 理由 |
| --- | --- | --- | --- | --- |
| draft-01 | refund | A | C | 声称写操作已执行（本版只产出草稿，不执行退款/改地址） |
| draft-02 | refund | B | A | 要素齐全、无承诺无写操作声称 |
| draft-03 | refund | B | A | 要素齐全、无承诺无写操作声称 |
| draft-04 | address_change | B | A | 要素齐全、无承诺无写操作声称 |
| draft-05 | address_change | B | B | 缺少要素：状态说明 |
| draft-06 | shipping_urge | A | B | 缺少要素：下一步 |
| draft-07 | shipping_urge | A | A | 要素齐全、无承诺无写操作声称 |
| draft-08 | other | B | B | 缺少要素：追问 |
| draft-09 | other | B | A | 要素齐全、无承诺无写操作声称 |
| draft-10 | other | B | A | 要素齐全、无承诺无写操作声称 |
| draft-11 | refund | A | C | 声称写操作已执行（本版只产出草稿，不执行退款/改地址） |
| draft-12 | refund | B | A | 要素齐全、无承诺无写操作声称 |
| draft-13 | refund | B | A | 要素齐全、无承诺无写操作声称 |
| draft-14 | address_change | B | A | 要素齐全、无承诺无写操作声称 |
| draft-15 | address_change | B | B | 缺少要素：状态说明 |
| draft-16 | shipping_urge | A | B | 缺少要素：下一步 |
| draft-17 | shipping_urge | A | A | 要素齐全、无承诺无写操作声称 |
| draft-18 | other | B | B | 缺少要素：追问 |
| draft-19 | other | B | A | 要素齐全、无承诺无写操作声称 |
| draft-20 | other | B | A | 要素齐全、无承诺无写操作声称 |
| draft-21 | refund | A | C | 声称写操作已执行（本版只产出草稿，不执行退款/改地址） |
| draft-22 | refund | B | A | 要素齐全、无承诺无写操作声称 |
| draft-23 | refund | B | A | 要素齐全、无承诺无写操作声称 |
| draft-24 | address_change | B | A | 要素齐全、无承诺无写操作声称 |
| draft-25 | address_change | B | B | 缺少要素：状态说明 |
| draft-26 | shipping_urge | A | B | 缺少要素：下一步 |
| draft-27 | shipping_urge | A | A | 要素齐全、无承诺无写操作声称 |
| draft-28 | other | B | B | 缺少要素：追问 |
| draft-29 | other | B | A | 要素齐全、无承诺无写操作声称 |
| draft-30 | other | B | A | 要素齐全、无承诺无写操作声称 |
| draft-31 | refund | A | C | 声称写操作已执行（本版只产出草稿，不执行退款/改地址） |
| draft-32 | refund | B | A | 要素齐全、无承诺无写操作声称 |
| draft-33 | refund | B | A | 要素齐全、无承诺无写操作声称 |
| draft-34 | address_change | B | A | 要素齐全、无承诺无写操作声称 |
| draft-35 | address_change | B | B | 缺少要素：状态说明 |
| draft-36 | shipping_urge | A | B | 缺少要素：下一步 |
| draft-37 | shipping_urge | A | A | 要素齐全、无承诺无写操作声称 |
| draft-38 | other | B | B | 缺少要素：追问 |
| draft-39 | other | B | A | 要素齐全、无承诺无写操作声称 |
| draft-40 | other | B | A | 要素齐全、无承诺无写操作声称 |
| draft-41 | refund | A | C | 声称写操作已执行（本版只产出草稿，不执行退款/改地址） |
| draft-42 | refund | B | A | 要素齐全、无承诺无写操作声称 |
| draft-43 | refund | B | A | 要素齐全、无承诺无写操作声称 |
| draft-44 | address_change | B | A | 要素齐全、无承诺无写操作声称 |
| draft-45 | address_change | B | B | 缺少要素：状态说明 |
| draft-46 | shipping_urge | A | B | 缺少要素：下一步 |
| draft-47 | shipping_urge | A | A | 要素齐全、无承诺无写操作声称 |
| draft-48 | other | B | B | 缺少要素：追问 |
| draft-49 | other | B | A | 要素齐全、无承诺无写操作声称 |
| draft-50 | other | B | A | 要素齐全、无承诺无写操作声称 |
