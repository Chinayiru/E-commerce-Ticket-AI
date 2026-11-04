# 评估报告 openai-eval_cases-20261105000534

## 环境

- provider: `openai`，model: `deepseek-v4.1-flash-1017`
- prompt: `v3` / `96d10657d0f5f086`
- dataset_hash: `e2dd52a46a78fc0dfc98a677b5a1c86647339194e74d7632910e33c7307ed03d`
- mock_data_hash: `85b0806efa45adeba2ca8dcf74a0bc4652a55ae0a24babd909410c7d33b29fdb`
- DEMO_NOW: `2026-11-04T12:00:00+08:00`，commit: `a59e8b7`
- 预算：max_steps=6，token_budget=6000，wall_clock_s=30.0

## 指标

- 用例数：24
- 分类准确率：95.83%
- 工具调用正确率：95.83%
- 参数正确率：100.00%
- 转人工准确率：83.33%（其中改地址 6/6）
- 降级用例：3
- 时延 P95：12469 ms，均值：6774.2 ms
- 单次平均成本：0.005038 元
- usage 来源：reported

## 逐例结果

| case_id | run_id | 意图 | 工具集合 | 参数 | 转人工 | 状态 | stop_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev-refund-simple-1 | 3d3c4dedade0 | refund ✅ | ✅ | ✅ | ❌ | degraded | invalid_output |
| dev-refund-simple-2 | 1fecd19f6777 | other ❌ | ✅ | ✅ | ❌ | degraded | invalid_output |
| dev-refund-simple-3 | 6ee3a1e0607c | refund ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-refund-complex-1 | 68f80db7154c | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-2 | eb1ccc61008c | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-3 | dbc954d22963 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-1 | 80a9a984b5a8 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-2 | e819400d2e14 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-3 | 62156506ff3f | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-1 | bf4950e02bc6 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-2 | 25a7602b7b25 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-3 | a359a5dce6d4 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-1 | f5bb7a4d205e | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-2 | fc2e70875663 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-3 | 2183a6c9b335 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-1 | 15894e27b7f8 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-2 | d357a57e2e74 | shipping_urge ✅ | ❌ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-3 | ba7c76b70a7d | shipping_urge ✅ | ✅ | ✅ | ❌ | degraded | invalid_output |
| dev-other-simple-1 | a07e7f2d1c00 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-2 | a216da43fd4d | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-3 | 5aff8389b554 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-1 | 5d054d9d738c | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-2 | fb50e530b250 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-3 | 27cd9fabca25 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
