# 评估报告 openai-eval_cases-20261105004840

## 环境

- provider: `openai`，model: `deepseek-v4.1-flash-1017`
- prompt: `v3` / `9708d77f90463c2f`
- dataset_hash: `04ec76457ad04c20bead799bcc56ab04c8f7ff13109b57c2d31abd00f161d0b8`
- mock_data_hash: `85b0806efa45adeba2ca8dcf74a0bc4652a55ae0a24babd909410c7d33b29fdb`
- DEMO_NOW: `2026-11-04T12:00:00+08:00`，commit: `dfe8477`
- 预算：max_steps=6，token_budget=6000，wall_clock_s=30.0

## 指标

- 用例数：24
- 分类准确率：100.00%
- 工具调用正确率：100.00%
- 参数正确率：100.00%
- 转人工准确率：91.67%（其中改地址 6/6）
- 降级用例：0
- 时延 P95：11078 ms，均值：6543.5 ms
- 单次平均成本：0.005561 元
- usage 来源：reported

## 逐例结果

| case_id | run_id | 意图 | 工具集合 | 参数 | 转人工 | 状态 | stop_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev-refund-simple-1 | a5be404094c8 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-2 | 3103a538fe98 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-3 | ac99cb84ff92 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-1 | ef6399e29c37 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-2 | 6315cccf98db | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-3 | aec409a7f6b9 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-1 | bb454a1f8f40 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-2 | 05c6f790ca3b | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-3 | 3c2d2614f85d | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-1 | ac7c6a6eea5f | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-2 | 260a9157204b | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-3 | fba77c45961f | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-1 | 79999e46baf8 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-2 | 1e17fe3b7fcb | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-3 | 8edef8afe74a | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-1 | 7e8dee50b8dd | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-2 | 994443c84fed | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-3 | b3b03d01c1ab | shipping_urge ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-other-simple-1 | 0391ab5b3b13 | other ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-other-simple-2 | c8964d20721d | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-3 | b8fe212cca1c | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-1 | 14340b17a784 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-2 | 9b7fdec72d34 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-3 | 12d0b024559b | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
