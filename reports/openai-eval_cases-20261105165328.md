# 评估报告 openai-eval_cases-20261105165328

> 自动指标仅表示与该数据集标注的一致性；不等于客服采纳或独立业务复核。历史评分的已知限制见 reports/review-2026-11-05.md。

## 环境

- provider: `openai`，model: `deepseek-v4.1-flash-1017`
- prompt: `v3` / `9708d77f90463c2f`
- dataset_hash: `ce37cbf676850636217c9f19f7aafda26bb4c8273c237654841409b181b78a23`
- mock_data_hash: `85b0806efa45adeba2ca8dcf74a0bc4652a55ae0a24babd909410c7d33b29fdb`
- DEMO_NOW: `2026-11-04T12:00:00+08:00`，commit: `2c19ba8`
- 预算：max_steps=6，token_budget=6000，wall_clock_s=30.0

## 指标

- 用例数：24
- 分类准确率：100.00%
- 工具调用正确率：95.83%
- 参数正确率：83.33%
- 转人工准确率：100.00%（计分 22/24，排除 2；其中改地址 6/6）
- 降级用例：0
- 时延 P95：11359 ms，均值：6520.0 ms
- 单次平均成本：0.005614 元
- usage 来源：reported

## 逐例结果

| case_id | run_id | 意图 | 工具集合 | 参数 | 转人工 | 状态 | stop_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev-refund-simple-1 | 689da7c2a34f | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-2 | 6ae4528ebd70 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-simple-3 | c25240b44eeb | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-1 | eda72a5f34ab | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-2 | d009aed855e8 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-refund-complex-3 | 05625743a513 | refund ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-1 | 744243f170eb | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-2 | d7dc35a5180b | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-simple-3 | ea4f7e22cca8 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-1 | d9c06416428d | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-2 | 717a84ccb232 | address_change ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-address-complex-3 | 7e76edce52b1 | address_change ✅ | ❌ | ❌ | ✅ | ok | finalized |
| dev-shipping-simple-1 | 3c7ee5007057 | shipping_urge ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-shipping-simple-2 | 7981c298fae6 | shipping_urge ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-shipping-simple-3 | 0f8610126b69 | shipping_urge ✅ | ✅ | ❌ | ✅ | ok | finalized |
| dev-shipping-complex-1 | 4309757d4866 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-2 | bd0b4c2cd666 | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-shipping-complex-3 | bfee6bcc505a | shipping_urge ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-simple-1 | 06e6d32ed5d6 | other ✅ | ✅ | ✅ | —（不计分） | ok | finalized |
| dev-other-simple-2 | 0b090afe035f | other ✅ | ✅ | ✅ | —（不计分） | ok | finalized |
| dev-other-simple-3 | 6471f6f54f8e | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-1 | f48561dc5207 | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-2 | e336e0193dbf | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
| dev-other-complex-3 | ec58c8d0e84a | other ✅ | ✅ | ✅ | ✅ | ok | finalized |
