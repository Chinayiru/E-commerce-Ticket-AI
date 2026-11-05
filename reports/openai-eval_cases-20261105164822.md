# 评估报告 openai-eval_cases-20261105164822

> 自动指标仅表示与该数据集标注的一致性；不等于客服采纳或独立业务复核。历史评分的已知限制见 reports/review-2026-11-05.md。

## 环境

- provider: `openai`，model: `deepseek-v4.1-flash-1017`
- prompt: `v3` / `9708d77f90463c2f`
- dataset_hash: `ce37cbf676850636217c9f19f7aafda26bb4c8273c237654841409b181b78a23`
- mock_data_hash: `85b0806efa45adeba2ca8dcf74a0bc4652a55ae0a24babd909410c7d33b29fdb`
- DEMO_NOW: `2026-11-04T12:00:00+08:00`，commit: `2c19ba8`
- 预算：max_steps=6，token_budget=6000，wall_clock_s=30.0

## 指标

- 用例数：24
- 分类准确率：100.00%
- 工具调用正确率：100.00%
- 参数正确率：25.00%
- 转人工准确率：100.00%（计分 22/24，排除 2；其中改地址 6/6）
- 降级用例：0
- 时延 P95：7969 ms，均值：5629.0 ms
- 单次平均成本：0.005613 元
- usage 来源：reported

## 逐例结果

| case_id | run_id | 意图 | 工具集合 | 参数 | 转人工 | 状态 | stop_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev-refund-simple-1 | ba376bb79aa7 | refund ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-refund-simple-2 | 6d5b3cd9dbb8 | refund ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-refund-simple-3 | 75e7f5749736 | refund ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-refund-complex-1 | 47f5109a9c3c | refund ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-refund-complex-2 | bb82c00a7896 | refund ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-refund-complex-3 | 58109b4e5f5d | refund ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-address-simple-1 | 0d10f60d5f43 | address_change ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-address-simple-2 | f2a171720199 | address_change ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-address-simple-3 | 5d12b862b9d0 | address_change ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-address-complex-1 | e5af3556675a | address_change ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-address-complex-2 | 84ac31b56fc5 | address_change ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-address-complex-3 | ae419369c77f | address_change ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-shipping-simple-1 | 3b5d3f5df620 | shipping_urge ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-shipping-simple-2 | 2da70702d482 | shipping_urge ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-shipping-simple-3 | 3745ecb4f237 | shipping_urge ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-shipping-complex-1 | 55b2001ebff0 | shipping_urge ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-shipping-complex-2 | 2c757b05b7ea | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-3 | 7ac84127742a | shipping_urge ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-other-simple-1 | 900033951b3c | other ✅ | ✅ | ✅ | —（不计分） | ok | finalized |
| dev-other-simple-2 | e43717fe9274 | other ✅ | ✅ | ✅ | —（不计分） | ok | finalized |
| dev-other-simple-3 | db07022b9ed9 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-1 | 97f4e920c248 | other ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-other-complex-2 | d30773505def | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-3 | fd74f4bac955 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
