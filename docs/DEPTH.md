# 深度登记 航班时刻运行台

- 规模：中型
- 核心规则：用机场 IANA 时区解析 DST 重叠与跳时，所有航链在 UTC 上校验先后和衔接。
- 使用者与工作流：运行数据员导入航段，确认机场时区，处理当地时刻歧义，构建 UTC 航链并核对转机。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 航段采信 | 导入航段并隔离重复冲突 | POST /api/legs/import | `app/modules/m1_legs/parser.py` `app/modules/m1_legs/keys.py` | `tests/test_m1_legs.py` |
| M2 机场时区 | 查询日期对应的时区版本 | POST /api/airports | `app/modules/m2_airports/registry.py` `app/modules/m2_airports/contracts.py` | `tests/test_m2_airports.py` |
| M3 当地时刻 | 解析偏移、重叠与跳时 | POST /api/local-time/resolve POST /api/local-time/review | `app/modules/m3_localtime/resolve.py` `app/modules/m3_localtime/evidence.py` | `tests/test_m3_localtime.py` |
| M4 UTC 航链 | 换算航段并校验先后顺序 | POST /api/itineraries/build POST /api/itineraries/chains | `app/modules/m4_itinerary/builder.py` `app/modules/m4_itinerary/candidates.py` `app/modules/m4_itinerary/validate.py` | `tests/test_m4_itinerary.py` |
| M5 衔接判定 | 核对航站楼换乘与等待，管理航司确认台账 | POST /api/connections/check POST /api/connections/check-chain POST /api/connections/confirm GET /api/connections/board | `app/modules/m5_connections/rules.py` `app/modules/m5_connections/assessment.py` `app/modules/m5_connections/windows.py` `app/modules/m5_connections/service.py` | `tests/test_m5_connections.py` |
| M6 批次导出 | 核对航段守恒并导出时刻 | POST /api/reconcile | `app/modules/m6_batches/compare.py` `app/modules/m6_batches/exporter.py` | `tests/test_m6_batches.py` |

## 陷阱登记

| TRAP | 现象 | 朴素实现会怎样 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-03 | 尾行记录不完整 | 半条航段进入换算 | 完整边界检查后隔离 | `app/modules/m1_legs/parser.py` | `tests/test_m1_legs.py::test_truncated_tail_detected` |
| TRAP-05 | 必填时刻缺失 | 空时间在深层报错 | 采信阶段给原因码和行号 | `app/modules/m1_legs/parser.py` | `tests/test_m1_legs.py::test_missing_time_quarantined` |
| TRAP-07 | 空当地时刻 | 被转换成午夜 | 空值不参与航链 | `app/modules/m1_legs/parser.py` | `tests/test_m1_legs.py::test_missing_time_quarantined` |
| TRAP-09 | 超大外部行程号 | JSON 数字往返丢精度 | 始终按字符串保形 | `app/modules/m1_legs/keys.py` | `tests/test_m1_legs.py::test_external_id_keeps_large_digits` |
| TRAP-11 | 偏移与 Z 混用 | 同一时刻先后次序错误 | 统一到 UTC 后输出 Z | `app/modules/m3_localtime/resolve.py` | `tests/test_m3_localtime.py::test_utc_serializes_with_z` |
| TRAP-12 | DST 重叠与跳时 | 重复小时覆盖或虚构时刻 | 往返验证并显式 fold | `app/modules/m3_localtime/resolve.py` | `tests/test_m3_localtime.py::test_dst_overlap_has_two_candidates` |
| TRAP-13 | 航段乱序 | 输入顺序被当成航程顺序 | 按 UTC 起飞时刻稳定排序 | `app/modules/m4_itinerary/builder.py` | `tests/test_m4_itinerary.py::test_order_by_utc_is_stable` |
| TRAP-14 | 同航段时刻冲突 | 后写覆盖原计划 | 冲突版本进入隔离区 | `app/modules/m1_legs/parser.py` | `tests/test_m1_legs.py::test_conflicting_duplicate_detected` |
| TRAP-23 | 衔接窗口端点 | 结束时刻被重复计入 | 使用半开区间 | `app/modules/m5_connections/windows.py` | `tests/test_m5_connections.py::test_half_open_window_excludes_end` |
| TRAP-25 | 时区版本重叠 | 随机选中一版偏移 | 多个生效版本立即拒绝 | `app/modules/m2_airports/registry.py` | `tests/test_m2_airports.py::test_overlapping_timezone_versions_rejected` |
| TRAP-26 | 回拨时刻两个解释 | 静默选一个 UTC，把赶不上的航班判成可转 | 全部候选传播为候选 UTC 航链，候选结论分叉时挂起 `PENDING_CONFIRMATION`，只对候选一致的连接出确定判定 | `app/modules/m4_itinerary/candidates.py` `app/modules/m5_connections/assessment.py` | `tests/test_m5_candidate_chains.py::test_diverging_candidates_are_pending_not_valid` |
| TRAP-27 | 跨候选混用时刻 | 等待时间拿 A 链到达配 B 链出发 | 等待只在具体候选 UTC 航链内逐段计算，再按连接聚合候选判定 | `app/modules/m5_connections/assessment.py` | `tests/test_m5_candidate_chains.py::test_each_candidate_waits_are_computed_on_full_utc_chain` |
| TRAP-28 | 航司晚到确认 | 旧判定继续挂在页面上误导交接 | 晚到确认先把旧判定整体置为 superseded，再按新到达 UTC 重算落新判定 | `app/modules/m5_connections/service.py` `app/store.py` | `tests/test_m5_confirmations.py::test_late_arrival_supersedes_old_determination_and_recomputes` |
| TRAP-29 | 同一确认重跑 | 重复确认刷出多轮判定 | 按 run+类型+航段+负载哈希去重，重跑幂等不新增确认也不新增判定 | `app/modules/m5_connections/service.py` `app/store.py` | `tests/test_m5_confirmations.py::test_same_confirmation_rerun_is_idempotent` |

## 判定纪律（交接前出结论的规则）

1. 当地时刻唯一（UNIQUE）：直接换算 UTC，可出确定结论。
2. 夏令时回拨重叠（AMBIGUOUS）：两个 UTC 候选都保留，传播成候选航链；所有候选链对同一连接结论一致才标 `DETERMINED`，分叉则标 `PENDING_CONFIRMATION` 等航司确认 fold。
3. 夏令时跳时（NONEXISTENT）：该墙上时间不存在，航段进隔离区，不虚构时刻。
4. 航司确认分两类：`fold` 确认消除候选链；`late_arrival` 用新到达 UTC 令旧判定失效并重算。确认记录与判定台账持久化在 SQLite，页面用徽标区分待确认 / 已判定 / 已失效。

## 对账规则

- 输入航段 = 有效航段 + 冲突航段 + 隔离航段。
- 行程航段 = 可衔接航段 + 不可衔接航段。
- 到达 UTC 必须晚于起飞 UTC，飞行时长不得超过 18 小时。

## 已知不覆盖

- 不计算天气和空管延误，输入只描述计划时刻。

