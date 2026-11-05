# 评估报告 openai-eval_cases-20261105165752

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
- 参数正确率：100.00%
- 转人工准确率：95.45%（计分 22/24，排除 2；其中改地址 6/6）
- 降级用例：1
- 时延 P95：16563 ms，均值：6522.4 ms
- 单次平均成本：0.005813 元
- usage 来源：reported

## 逐例结果

| case_id | run_id | 意图 | 工具集合 | 参数 | 转人工 | 状态 | stop_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev-refund-simple-1 | 8526ddf73710 | refund ✅ | ✅ | ✅ | ❌ | degraded | token_budget |
| dev-refund-simple-2 | 49127d646bf3 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-3 | c5a35b384852 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-1 | 19cba89d42c1 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-2 | ae42e09dd8d2 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-3 | a79fc9323190 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-1 | b32a397ec977 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-2 | 78f857b1f054 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-3 | 8286e28ef58f | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-1 | 1be2b53d90e8 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-2 | 59d2a330af75 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-3 | b9e85ce4325f | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-1 | b33bb4b5a6c3 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-2 | 9fa2be46a5bf | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-3 | efdc46bd7b52 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-1 | 4b747e92645e | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-2 | ee3c4f23b3a0 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-3 | af99941a604f | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-1 | 20e6fae6dd67 | other ✅ | ✅ | ✅ | —（不计分） | ok | finalized |
| dev-other-simple-2 | eda8ac2aea46 | other ✅ | ✅ | ✅ | —（不计分） | ok | finalized |
| dev-other-simple-3 | 5443dfc894f2 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-1 | b570a439c6a5 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-2 | 66800b428b81 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-3 | 5229cccd6335 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
