# 评估报告 openai-eval_cases-20261105004445

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
- 工具调用正确率：95.83%
- 参数正确率：100.00%
- 转人工准确率：91.67%（其中改地址 6/6）
- 降级用例：0
- 时延 P95：12890 ms，均值：6971.4 ms
- 单次平均成本：0.006078 元
- usage 来源：reported

## 逐例结果

| case_id | run_id | 意图 | 工具集合 | 参数 | 转人工 | 状态 | stop_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev-refund-simple-1 | 6e8b3ed7ca28 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-2 | a00731086db6 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-3 | 9ca1728cdca0 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-1 | 03ab64ddfd6b | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-2 | 36fd470d248c | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-3 | cc64818cf693 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-1 | d1310c4d8da8 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-2 | bd7eb2589c1e | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-3 | 4a605f3525d2 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-1 | 127d3b088fa0 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-2 | c4ca3cadf182 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-3 | f4d2c7aa11d0 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-1 | e8861dba5a21 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-2 | f6efd90d4488 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-3 | c0965a011c42 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-1 | 93e6c27498f4 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-2 | 6bc9d790f9ed | shipping_urge ✅ | ❌ | ✅ | ❌ | ok | finalized |
| dev-shipping-complex-3 | 6c3897d4de5a | shipping_urge ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-other-simple-1 | 99fa81fa3b0f | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-2 | b8ff63893307 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-3 | df06727436e2 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-1 | 82ed95af0c69 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-2 | e989c7483c21 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-3 | 21b89bb4afe1 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
