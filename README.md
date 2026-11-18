# 航班时刻运行台

面向真实数据复核的中型数据工程工具，包含六个可独立调用的业务模块。规则、失败原因与证据字段见 docs/DATA-DICTIONARY.md，陷阱和测试映射见 docs/DEPTH.md。

## 启动

docker compose up --build

浏览器访问 http://localhost:18219。测试：docker compose exec -T app pytest -q

## 模块

- M1 航段采信：页面 /legs，接口 /api/legs/import
- M2 机场时区：页面 /airports，接口 /api/airports
- M3 当地时刻：页面 /local-time，接口 /api/local-time/resolve（候选审查 /api/local-time/review）
- M4 UTC 航链：页面 /itineraries，接口 /api/itineraries/build（候选航链 /api/itineraries/chains）
- M5 衔接判定：页面 /connections，接口 /api/connections/check（整链 /check-chain、航司确认 /confirm、台账 /board）
- M6 批次导出：页面 /batches，接口 /api/reconcile

## 夏令时与判定纪律

回拨重叠的当地时刻有两个 UTC 解释：系统保留全部候选并传播成候选 UTC 航链，不在采信时静默二选一。所有候选链对同一衔接给出一致结论时才下 `DETERMINED`；结论分叉则挂 `PENDING_CONFIRMATION`，先放行能确定的连接，分叉项等航司确认 fold，避免把赶不上的航班判成可转。航司晚到确认（late_arrival）会令旧判定失效（superseded）并按整条 UTC 航链重算；同一条确认重跑幂等。确认报文样例见 sample_data/confirmations.json。

## 运行规则

同一输入内容生成相同运行标识，重复执行复用已有批次。隔离记录包含原因码、原始行号与原值；业务导出只保留一份证据清单。

