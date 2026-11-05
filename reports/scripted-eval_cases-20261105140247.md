# 评估报告 scripted-eval_cases-20261105140247

## 环境

- provider: `scripted`，model: `scripted`
- prompt: `v3` / `9708d77f90463c2f`
- dataset_hash: `ce37cbf676850636217c9f19f7aafda26bb4c8273c237654841409b181b78a23`
- mock_data_hash: `85b0806efa45adeba2ca8dcf74a0bc4652a55ae0a24babd909410c7d33b29fdb`
- DEMO_NOW: `2026-11-04T12:00:00+08:00`，commit: `8b025a6`
- 预算：max_steps=6，token_budget=6000，wall_clock_s=30.0

## 指标

- 用例数：24
- 分类准确率：100.00%
- 工具调用正确率：100.00%
- 参数正确率：100.00%
- 转人工准确率：100.00%（其中改地址 6/6）
- 降级用例：0
- 时延 P95：63 ms，均值：46.8 ms
- 单次平均成本：None 元
- usage 来源：scripted

## 逐例结果

| case_id | run_id | 意图 | 工具集合 | 参数 | 转人工 | 状态 | stop_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev-refund-simple-1 | 0ed7597669f6 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-2 | efa624633768 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-3 | 7c894800b2f2 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-1 | ae94a183de27 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-2 | ece9eedf1046 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-3 | 3fe69bc451cb | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-1 | 2cda24d689f3 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-2 | 92f2a38e795e | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-3 | 03120b9f6ccc | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-1 | b5161981333b | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-2 | d0c75160bede | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-3 | 2a5393297a3a | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-1 | 6aa15247c503 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-2 | 7d3c9ca7cfc8 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-3 | 73cf80aa7c64 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-1 | 45482219689f | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-2 | 350c30312423 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-3 | 3df57d804041 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-1 | c823f9da70fa | other ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-other-simple-2 | e8dddfd464c0 | other ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-other-simple-3 | 51cfe7997e07 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-1 | 3ec50e300b79 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-2 | 168a3480f0a2 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-3 | c2f83dec6450 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
