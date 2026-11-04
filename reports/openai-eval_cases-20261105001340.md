# 评估报告 openai-eval_cases-20261105001340

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
- 工具调用正确率：100.00%
- 参数正确率：100.00%
- 转人工准确率：87.50%（其中改地址 6/6）
- 降级用例：0
- 时延 P95：8422 ms，均值：6063.9 ms
- 单次平均成本：0.005474 元
- usage 来源：reported

## 逐例结果

| case_id | run_id | 意图 | 工具集合 | 参数 | 转人工 | 状态 | stop_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev-refund-simple-1 | fa72c2c56433 | refund ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-refund-simple-2 | 6d6ca4005fbd | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-3 | 8be63193d205 | refund ✅ | ✅ | ✅ | ❌ | ok | finalized |
| dev-refund-complex-1 | 9b681bcadcae | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-2 | e5ccf8f9d868 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-3 | 13aa003da612 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-1 | 7118eb275080 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-2 | fd8def4a91ea | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-3 | 3a6e811e17b3 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-1 | 226e54e07036 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-2 | e49eaf61dbcf | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-3 | ee5eb9535ede | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-1 | 6b7c830ae796 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-2 | aa65e0636b93 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-simple-3 | 4a234004b751 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-1 | e82c08cc0b38 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-2 | 323e062ebaa9 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-3 | dfe71296214d | other ❌ | ✅ | ✅ | ❌ | ok | finalized |
| dev-other-simple-1 | fb5e5f88cf9b | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-2 | 35b46a415d6e | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-3 | 9535be6ef915 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-1 | e5233844065d | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-2 | 3cb61937355e | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-3 | af6f14b7d7cd | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
