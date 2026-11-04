# 评估报告 scripted-eval_cases-20261104234702

## 环境

- provider: `scripted`，model: `scripted`
- prompt: `v3` / `a9b2d3d5270090e1`
- dataset_hash: `e2dd52a46a78fc0dfc98a677b5a1c86647339194e74d7632910e33c7307ed03d`
- mock_data_hash: `85b0806efa45adeba2ca8dcf74a0bc4652a55ae0a24babd909410c7d33b29fdb`
- DEMO_NOW: `2026-11-04T12:00:00+08:00`，commit: `f3b369c`
- 预算：max_steps=6，token_budget=6000，wall_clock_s=30.0

## 指标

- 用例数：24
- 分类准确率：100.00%
- 工具调用正确率：100.00%
- 参数正确率：100.00%
- 转人工准确率：100.00%（其中改地址 6/6）
- 降级用例：0
- 时延 P95：78 ms，均值：48.9 ms
- 单次平均成本：None 元
- usage 来源：scripted

## 逐例结果

| case_id | run_id | 意图 | 工具集合 | 参数 | 转人工 | 状态 | stop_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev-refund-simple-1 | db4856a8f159 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-2 | 30dbf3bf2eb7 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-3 | b45b98815e10 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-1 | c1aadec45697 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-2 | 604c3b091816 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-3 | ac249093a88a | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-1 | fc400a3db03f | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-2 | 5cdec3f8cb34 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-3 | 4c1abc91fec0 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-1 | e847d14f4293 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-2 | 23ddf9940fc9 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-3 | 0f8596adf23a | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-1 | b6ce3945b480 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-2 | 9ebf2899fa2d | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-3 | 09b1fb0d9b56 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-1 | 82a7bac9db1d | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-2 | fab4acb0db56 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-3 | 765070070935 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-1 | 05435739ae54 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-2 | 70d755fb801c | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-3 | 2c33ebe321ba | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-1 | 5b33d41fb569 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-2 | bc870b76c622 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-3 | 248081fdfddc | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
