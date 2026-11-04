# 评估报告 openai-eval_cases-20261105001018

## 环境

- provider: `openai`，model: `deepseek-v4.1-flash-1017`
- prompt: `v3` / `96d10657d0f5f086`
- dataset_hash: `e462f3f96a9883527fc9309c35cb5848c8b1ec73e5f4a6ef3aac53bd96bc1260`
- mock_data_hash: `85b0806efa45adeba2ca8dcf74a0bc4652a55ae0a24babd909410c7d33b29fdb`
- DEMO_NOW: `2026-11-04T12:00:00+08:00`，commit: `a59e8b7`
- 预算：max_steps=6，token_budget=6000，wall_clock_s=30.0

## 指标

- 用例数：24
- 分类准确率：95.83%
- 工具调用正确率：95.83%
- 参数正确率：100.00%
- 转人工准确率：83.33%（其中改地址 6/6）
- 降级用例：0
- 时延 P95：14453 ms，均值：5993.5 ms
- 单次平均成本：0.005844 元
- usage 来源：reported

## 逐例结果

| case_id | run_id | 意图 | 工具集合 | 参数 | 转人工 | 状态 | stop_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev-refund-simple-1 | 446436a1c290 | refund ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-refund-simple-2 | f4edc002eba1 | refund ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-refund-simple-3 | e8af6ee08e9b | refund ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-refund-complex-1 | 054960af0203 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-2 | a3313624f091 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-3 | 6152499b62be | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-1 | 8752426e95b9 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-2 | 7784441a16dc | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-3 | dafb92f0504a | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-1 | ab0f303d6106 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-2 | 4e82c2ea21c4 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-3 | 2fa2ccb109ea | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-1 | 02bdff412202 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-2 | 62f19eb784e4 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-3 | be3f6821e6f0 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-1 | c51c4fe0b3c3 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-2 | 9b720d59e12d | shipping_urge ✅ | ❌ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-3 | 8f52607aaed3 | other ❌ | ✅ | ✅ | ❌ | ok | finalized |
| dev-other-simple-1 | f96e27ea0793 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-2 | 377526b113c4 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-3 | 7930d504ed07 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-1 | 42fde449f049 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-2 | 3106ebe87125 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-3 | 05919b5067be | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
