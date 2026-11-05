# 评估报告 scripted-eval_cases-20261105221334

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
- 时延 P95：171 ms，均值：61.8 ms
- 单次平均成本：None 元
- usage 来源：scripted

## 逐例结果

| case_id | run_id | 意图 | 工具集合 | 参数 | 转人工 | 状态 | stop_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev-refund-simple-1 | 62b9b3f4ace6 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-2 | e8d04e8c68e6 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-3 | 16b4c4fa9606 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-1 | 923bf1d6f459 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-2 | 81e66f15c4b6 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-3 | abb32e1cba12 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-1 | 202b1d4563d7 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-2 | 0e5de4b3bddc | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-3 | 8469e443ed9a | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-1 | e0a684cd6c0d | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-2 | 76a112feeb48 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-3 | f73ad693cbbb | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-1 | 972964a87d01 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-2 | 0a6d7c872b9d | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-3 | ec702364dcd0 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-1 | d80fb3dc6d35 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-2 | 46244d4fe0bc | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-3 | 7fa58e4e6543 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-1 | 0d1057f664b6 | other ✅ | ✅ | ✅ | —（不计分） | ok | finalized |
| dev-other-simple-2 | 791b341c735a | other ✅ | ✅ | ✅ | —（不计分） | ok | finalized |
| dev-other-simple-3 | 8380b086e741 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-1 | 550393a1c24c | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-2 | 037441864a04 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-3 | 37ecd4253c84 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
