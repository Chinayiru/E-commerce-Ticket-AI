# 评估报告 openai-eval_cases-20261105001648

## 环境

- provider: `openai`，model: `deepseek-v4.1-flash-1017`
- prompt: `v3` / `96d10657d0f5f086`
- dataset_hash: `04ec76457ad04c20bead799bcc56ab04c8f7ff13109b57c2d31abd00f161d0b8`
- mock_data_hash: `85b0806efa45adeba2ca8dcf74a0bc4652a55ae0a24babd909410c7d33b29fdb`
- DEMO_NOW: `2026-11-04T12:00:00+08:00`，commit: `a59e8b7`
- 预算：max_steps=6，token_budget=6000，wall_clock_s=30.0

## 指标

- 用例数：24
- 分类准确率：91.67%
- 工具调用正确率：100.00%
- 参数正确率：100.00%
- 转人工准确率：83.33%（其中改地址 6/6）
- 降级用例：1
- 时延 P95：14719 ms，均值：6152.5 ms
- 单次平均成本：0.005404 元
- usage 来源：reported

## 逐例结果

| case_id | run_id | 意图 | 工具集合 | 参数 | 转人工 | 状态 | stop_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev-refund-simple-1 | b3575234a397 | refund ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-refund-simple-2 | 6680f2e401c3 | other ❌ | ✅ | ✅ | ❌ | degraded | invalid_output |
| dev-refund-simple-3 | bd4d79a0a71e | refund ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-refund-complex-1 | 1907dd8f5558 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-2 | 7a65e3b9bcde | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-3 | cf3ce3f336a9 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-1 | 73e1009a5a2c | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-2 | 4cf132a8a2e8 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-3 | 46e23fdce8ed | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-1 | 6d18d1565eca | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-2 | 6041d9a18713 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-3 | 114a538eef6a | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-1 | bb8554088f2b | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-2 | 589fb5354e8c | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-3 | f5f19ab01490 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-1 | dbaf9f66cb0a | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-2 | 5eed5253ce38 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-3 | cb0a249d7512 | other ❌ | ✅ | ✅ | ❌ | ok | finalized |
| dev-other-simple-1 | 4e3646c1fb96 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-2 | d69f0a297cc9 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-3 | dccfab8fcbe5 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-1 | 00393965b4c6 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-2 | 96d06a4e30cd | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-3 | a15140e9b7ec | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
