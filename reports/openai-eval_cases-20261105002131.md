# 评估报告 openai-eval_cases-20261105002131

## 环境

- provider: `openai`，model: `deepseek-v4.1-flash-1017`
- prompt: `v3` / `96d10657d0f5f086`
- dataset_hash: `04ec76457ad04c20bead799bcc56ab04c8f7ff13109b57c2d31abd00f161d0b8`
- mock_data_hash: `85b0806efa45adeba2ca8dcf74a0bc4652a55ae0a24babd909410c7d33b29fdb`
- DEMO_NOW: `2026-11-04T12:00:00+08:00`，commit: `a59e8b7`
- 预算：max_steps=6，token_budget=6000，wall_clock_s=30.0

## 指标

- 用例数：24
- 分类准确率：95.83%
- 工具调用正确率：95.83%
- 参数正确率：100.00%
- 转人工准确率：91.67%（其中改地址 6/6）
- 降级用例：0
- 时延 P95：9062 ms，均值：6147.1 ms
- 单次平均成本：0.005673 元
- usage 来源：reported

## 逐例结果

| case_id | run_id | 意图 | 工具集合 | 参数 | 转人工 | 状态 | stop_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev-refund-simple-1 | abf5c9319463 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-2 | e354d55a452e | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-3 | f1c5da14bd28 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-1 | bee023ca214f | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-2 | d3253b9f9a92 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-3 | ecf3bf1b575f | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-1 | b8619478dfee | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-2 | f24bfcc5ee75 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-3 | 3e9ab8e49fe7 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-1 | 498a9f42703d | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-2 | 0044fcc47339 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-3 | 863ffd3f618e | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-1 | 554368c5db9e | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-2 | 51d69caec7a1 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-3 | d229ebfee472 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-1 | dc1cb2ec4498 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-2 | cf6dce5d05d2 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-3 | 5dc571fd4460 | other ❌ | ✅ | ✅ | ❌ | ok | finalized |
| dev-other-simple-1 | 6c3f0d9444ee | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-2 | 69809a05a0de | other ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-other-simple-3 | ee4626e9d825 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-1 | 6094b8dec452 | other ✅ | ❌ | ✅ | ✅ | ok | finalized |
| dev-other-complex-2 | 59f917d10bf9 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-3 | 30bef7b0cf67 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
