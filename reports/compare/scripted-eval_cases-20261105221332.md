# 评估报告 scripted-eval_cases-20261105221332

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
- 时延 P95：78 ms，均值：50.7 ms
- 单次平均成本：None 元
- usage 来源：scripted

## 逐例结果

| case_id | run_id | 意图 | 工具集合 | 参数 | 转人工 | 状态 | stop_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev-refund-simple-1 | e22abf6fa1bf | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-2 | 10e38d73a937 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-3 | 78b7962146ea | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-1 | 6ad0f8e6668e | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-2 | 2384c636d69c | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-3 | 04a366d9e609 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-1 | 68f1cd013c9c | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-2 | 261941eb3529 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-3 | 47fb92d27a5f | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-1 | 922f15bca664 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-2 | b191df1f24df | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-3 | dc3a409f06f2 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-1 | b8b8838eff00 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-2 | 1c74e7111a2a | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-3 | 88e35d8da5cc | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-1 | 46a7264f20c1 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-2 | 73c61d7927c7 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-3 | 843dde0d37d9 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-1 | 9121bce324c0 | other ✅ | ✅ | ✅ | —（不计分） | ok | finalized |
| dev-other-simple-2 | 89c37c75caaa | other ✅ | ✅ | ✅ | —（不计分） | ok | finalized |
| dev-other-simple-3 | dc1260d635b8 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-1 | 2e1b36cb7e9b | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-2 | c6ca6b48943c | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-3 | 81989aacbb52 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
