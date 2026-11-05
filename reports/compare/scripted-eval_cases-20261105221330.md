# 评估报告 scripted-eval_cases-20261105221330

> 自动指标仅表示与该数据集标注的一致性；不等于客服采纳或独立业务复核。历史评分的已知限制见 reports/review-2026-11-05.md。

## 环境

- provider: `scripted`，model: `scripted`
- prompt: `v3` / `9708d77f90463c2f`
- dataset_hash: `ce37cbf676850636217c9f19f7aafda26bb4c8273c237654841409b181b78a23`
- mock_data_hash: `85b0806efa45adeba2ca8dcf74a0bc4652a55ae0a24babd909410c7d33b29fdb`
- DEMO_NOW: `2026-11-04T12:00:00+08:00`，commit: `f48421b`
- 预算：max_steps=6，token_budget=6000，wall_clock_s=30.0

## 指标

- 用例数：24
- 分类准确率：100.00%
- 工具调用正确率：100.00%
- 参数正确率：100.00%
- 转人工准确率：100.00%（计分 22/24，排除 2；其中改地址 6/6）
- 降级用例：0
- 时延 P95：78 ms，均值：52.0 ms
- 单次平均成本：None 元
- usage 来源：scripted

## 逐例结果

| case_id | run_id | 意图 | 工具集合 | 参数 | 转人工 | 状态 | stop_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev-refund-simple-1 | f6b83ac5be1f | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-2 | 74f64bd09a85 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-3 | e54581c2b00f | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-1 | e9ed469018fe | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-2 | 484d06a0bb8b | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-3 | 33104ea1d1cf | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-1 | 095c1eeaf1b9 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-2 | 1d2a748d2704 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-3 | 5d7a939abda7 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-1 | f34373fd2b5d | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-2 | 5d8d0576aba4 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-3 | 1a12119ce5e3 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-1 | 9f3e73c948bb | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-2 | d1a2f4c49cf9 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-3 | e9f6c1236afa | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-1 | f8f46e5d7ff7 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-2 | 8f7ca188b448 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-3 | 26ef1a9b8519 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-1 | 404d62630ef2 | other ✅ | ✅ | ✅ | —（不计分） | ok | finalized |
| dev-other-simple-2 | c7bb7267827a | other ✅ | ✅ | ✅ | —（不计分） | ok | finalized |
| dev-other-simple-3 | 5b2fc627acb8 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-1 | 1cfd771c0339 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-2 | 052d3ca15822 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-3 | 5937757929d2 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
