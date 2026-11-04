# 评估报告 openai-eval_cases-20261104235912

## 环境

- provider: `openai`，model: `deepseek-v4.1-flash-1017`
- prompt: `v3` / `a9b2d3d5270090e1`
- dataset_hash: `e2dd52a46a78fc0dfc98a677b5a1c86647339194e74d7632910e33c7307ed03d`
- mock_data_hash: `85b0806efa45adeba2ca8dcf74a0bc4652a55ae0a24babd909410c7d33b29fdb`
- DEMO_NOW: `2026-11-04T12:00:00+08:00`，commit: `a59e8b7`
- 预算：max_steps=6，token_budget=6000，wall_clock_s=30.0

## 指标

- 用例数：24
- 分类准确率：95.83%
- 工具调用正确率：75.00%
- 参数正确率：79.17%
- 转人工准确率：58.33%（其中改地址 6/6）
- 降级用例：0
- 时延 P95：12313 ms，均值：7731.7 ms
- 单次平均成本：0.005418 元
- usage 来源：reported

## 逐例结果

| case_id | run_id | 意图 | 工具集合 | 参数 | 转人工 | 状态 | stop_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev-refund-simple-1 | bce169f47326 | refund ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-refund-simple-2 | be18724b7e9c | refund ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-refund-simple-3 | d1305e88b126 | refund ✅ | ❌ | ❌ | ❌ | ok | finalized |
| dev-refund-complex-1 | 2e5c648276f5 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-2 | 7b4f998ded47 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-3 | a3d8bef3147a | refund ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-address-simple-1 | 84bf1cd3cb14 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-2 | 36b10134f55c | address_change ✅ | ❌ | ✅ | ✅ | ok | finalized |
| dev-address-simple-3 | 87889dbf55c1 | address_change ✅ | ❌ | ✅ | ✅ | ok | finalized |
| dev-address-complex-1 | fd22f81c4af9 | address_change ✅ | ❌ | ✅ | ✅ | ok | finalized |
| dev-address-complex-2 | f3039c649093 | address_change ✅ | ❌ | ✅ | ✅ | ok | finalized |
| dev-address-complex-3 | d3b3b4ed83f2 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-1 | f292bdc974bd | shipping_urge ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-shipping-simple-2 | 0171f5268c37 | shipping_urge ✅ | ✅ | ❌ | ❌ | ok | finalized |
| dev-shipping-simple-3 | c8ccea683e3a | shipping_urge ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-shipping-complex-1 | 2808654287b4 | shipping_urge ✅ | ✅ | ❌ | ❌ | ok | finalized |
| dev-shipping-complex-2 | 249cbda0f695 | shipping_urge ✅ | ❌ | ✅ | ❌ | ok | finalized |
| dev-shipping-complex-3 | e1afc019309e | other ❌ | ✅ | ✅ | ❌ | ok | finalized |
| dev-other-simple-1 | 9253b91d282a | other ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-other-simple-2 | 41de08881e95 | other ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-other-simple-3 | 812ef0cf9f74 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-1 | 86216d70ac63 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-2 | 59b5bfcda696 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-3 | b4edc1909195 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
