# 评估报告 scripted-eval_cases-20261104234428

## 环境

- provider: `scripted`，model: `scripted`
- prompt: `v3` / `a9b2d3d5270090e1`
- dataset_hash: `e2dd52a46a78fc0dfc98a677b5a1c86647339194e74d7632910e33c7307ed03d`
- mock_data_hash: `85b0806efa45adeba2ca8dcf74a0bc4652a55ae0a24babd909410c7d33b29fdb`
- DEMO_NOW: `2026-11-04T12:00:00+08:00`，commit: `6da9481`
- 预算：max_steps=6，token_budget=6000，wall_clock_s=30.0

## 指标

- 用例数：24
- 分类准确率：100.00%
- 工具调用正确率：100.00%
- 参数正确率：100.00%
- 转人工准确率：100.00%（其中改地址 6/6）
- 降级用例：0
- 时延 P95：78 ms，均值：49.5 ms
- 单次平均成本：None 元
- usage 来源：scripted

## 逐例结果

| case_id | run_id | 意图 | 工具集合 | 参数 | 转人工 | 状态 | stop_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev-refund-simple-1 | 50eae265b7b5 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-2 | d35a0f61e386 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-3 | 41842febf2d8 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-1 | 0fa6b1cd51cb | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-2 | 81eb32c2fec5 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-3 | 8f0cd4c2b6f8 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-1 | 8244be84c664 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-2 | bae58196fd4f | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-3 | 27039655627d | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-1 | 0d59808f80e0 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-2 | fc4be4916767 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-3 | 79c96d86dd9d | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-1 | 54f5c58d1fca | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-2 | 103afc75e4b2 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-3 | af90becf4fb2 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-1 | f45faae16157 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-2 | 38e319143437 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-3 | 6cd8fe1eebc7 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-1 | eaaaacdd6336 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-2 | 36c53640ca29 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-3 | e5e764859f75 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-1 | 105ef8705c57 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-2 | 8ee13814e392 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-3 | 0732523bcfdf | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
