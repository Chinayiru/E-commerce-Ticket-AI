# 评估报告 openai-eval_cases-20261105135744

## 环境

- provider: `openai`，model: `deepseek-v4.1-flash-1017`
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
- 时延 P95：11063 ms，均值：6110.6 ms
- 单次平均成本：0.005798 元
- usage 来源：reported

## 逐例结果

| case_id | run_id | 意图 | 工具集合 | 参数 | 转人工 | 状态 | stop_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev-refund-simple-1 | 046f1767bcb3 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-2 | fea7f4ad3fa1 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-3 | d5974aa9556a | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-1 | c32c00a7aa88 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-2 | 6e32fc33ad0a | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-3 | f51b37692427 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-1 | c56cbce65e4b | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-2 | e5c3a32a9f7f | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-3 | a19372691997 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-1 | cff59fead014 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-2 | 4db515c598af | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-3 | 4cc423fafdf1 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-1 | ce6a8f969c33 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-2 | f1d0758d2ca5 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-3 | cfaf6f8a34c1 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-1 | 8f9bba5dfa46 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-2 | 47806dc893ba | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-3 | a43ed5d083c2 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-1 | 083da578e8bc | other ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-other-simple-2 | 2a03482a5c22 | other ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-other-simple-3 | 62cbbc98414a | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-1 | 7a5ebe3962b5 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-2 | 527c86ac97bb | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-3 | 5562a9cf1d2f | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
