# 数据字典

- run_id：规则版本与输入 SHA-256 前 12 位组成的稳定批次标识。
- line_no：从 1 开始的物理来源行号，不因隔离或排序改变。
- business_key：本项目声明的业务唯一键，始终按字符串存储。
- reason_code：隔离原因的稳定英文编码。
- accepted：进入业务计算的记录数。
- quarantined：保留证据但不参与业务计算的记录数。
- 数值：金额、税额、用量和权重使用 Decimal；对外序列化为字符串。
- 时间：存储为带偏移的 ISO 8601，分桶使用半开区间。
- 空值：缺失键、空串和业务哨兵分别记录。
- 幂等：完整输入字节与规则版本相同则复用 run_id，不新增结果。
- fold：夏令时回拨重叠小时的解释序号，0=较早的 UTC 瞬间，1=较晚的 UTC 瞬间；未确认时为 null。
- candidate_count：一个当地时刻在 IANA 时区下的 UTC 候选数，唯一时刻为 1，回拨重叠为 2，跳时为 0。
- decision：衔接判定纪律字段。DETERMINED=所有候选 UTC 航链结论一致可交接；PENDING_CONFIRMATION=候选结论分叉，等航司确认。
- superseded：判定失效标记。航司晚到确认到达后旧判定置 1，重算结果写入新判定轮次（determination_id 末尾 r{n}）。
- 确认幂等键：(run_id, kind, leg_key, payload_hash) 唯一；同一条确认重跑不新增 confirmations 与 determinations 行。
- leg_key：航段业务键，格式 `航班号|航班日期|出发机场|到达机场`，按字符串存储。
- 衔接等待：只在具体候选 UTC 航链内用相邻航段的到达/出发 UTC 相减，禁止跨候选混用时刻。

