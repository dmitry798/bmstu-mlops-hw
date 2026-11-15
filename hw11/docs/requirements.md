# Пунктовый аудит homework11.html

Итоговые значения и PASS/FAIL: [results/audit.json](../results/audit.json). Проверка не объявляет отсутствующие данные выполненными. Видео записывается только после PASS.

| Требование | Реализация / доказательство |
|---|---|
| Продолжение ДЗ8–10, CPU simulated | Dockerfile копирует прежние service_core/release; app/server.py, backend_mode в каждом нагрузочном ответе |
| Docker, Helm, 2 replica, Service, ConfigMap, requests/limits, values | charts/hw11, Dockerfile; preflight/pods-before-b.json и images.json |
| Разные startup/readiness/liveness; warmup20s | api.yaml; a-broken-proof/a-fixed-proof schedules+requests, pod-logs и kubernetes-timeline.jsonl |
| Артефакт, SHA, фактическая версия, восстановление | immutable model-A/B.yaml; прежний release.verify_files; kubernetes-checks.json replacement_same_artifact |
| RequestID/Pod/model, внешняя история | NDJSON/заголовки, pod-logs; check-dialogues/check-replacement requests |
| Prometheus/Grafana, per-Pod discovery и экспорт | monitoring/prometheus.yaml, stack.yaml, dashboard-export.json |
| A исходный дефект и одинаковый повтор | одинаковые32s×2rps списки a-broken-proof и a-fixed-proof; checks-a-repeat.json |
| A длительный поток до rollout; новый warmup; grace | a-healthy-long-0/1, a-healthy-rollout, checks-a-repeat.json; drain pod-logs; Ready/EndpointSlice timeline |
| A плохая B исключена, откат A по ответам | a-bad-b/a-rollback requests; checks-a.json (соответствующие проверки) |
| A полный штатный прогон0HTTP5xx/0incomplete | a-healthy-rollout +2long:15/15 completed; checks-a-repeat.json |
| A аварийный kill, обрыв, detection/recovery; retries separate | check-force-kill requests, kubernetes-checks.json; restart/Ready timeline; attempt=1 без скрытых retry |
| B два Service над теми же Pod, сеть/IP, keepalive | api.yaml, preflight/network.txt, pod-logs peer_ip; client.py disables keepalive |
| B >=4 client Pod/IP; uniform и80% | charts clients.yaml, schedules and client_ip fields; audit.json |
| B одинаковые запросы/длины/ответы/расписания | audit сравнивает SHA256 полных items для всех policy/repetition в каждом traffic |
| B ограниченный локальный кеш, hit/miss/concurrency | core.py LRU8, values .015/.14 CPU sec, MAX_RUNNING1/MAX_WAITING6; report |
| B распределение/очередь/TTFC поPod; hot vs spare | b_sticky_skew requests, per-Pod gauges, plot2; raw results include uniform/no-skew |
| B исправление и повтор, локальность/ограничения engine | fixed Service=None, все3повтораuniform/skew; report+review |
| B каждое policy×traffic 3раза >=120s; cache/warmup |18 отдельных файлов schedule/summary/requests; admin/reset на idle; измерен send lag |
| C HPA v2 min2/max3 CPU, metrics API/requests, real compute | hpa.yaml; metrics-api.json/api-resource-requests.json; cpu_burn thread_time |
| C2→3 Ready/creation→2 stabilization фактически | c-events.json, kubernetes-timeline.jsonl, plot4; c-hpa-analysis.json |
| C повтор hot и средняяCPU/newPod мало работы | c-hot requests, report, CPU query range, c-hpa-analysis.json |
| C2алерта minimum sample+for, pending/firing/recovery | alerts.yaml; c-alert-states.jsonl; audit transition assertion |
| Монотонные времена send/first/finish, части/статус/pod/model | requests.jsonl и отдельные фазы; inter_chunk_seconds; simulated TTFC terminology |
| Plan/sent/done/reject/abort/expired/errors + p50/p95+n/fractions | summary-файлы, statistics.json; report таблица; audit balance check |
| Histogram buckets, sum(le), samecohort client comparison | queries.promql; phase-scoped snapshot; histogram-comparison.json exact counts |
| Dashboard latency/total/queue/running/RPS/errors/CPU/RAM/Ready | dashboard.json/export; actualGrafana /d/hw11; per-Pod series |
| Labels bounded, no IDs | PHASES whitelist; IDs только request logs, app/server.py |
| >=5checks,3liveK8s, accounting/isolation RED/GREEN | scripts/kubernetes_checks.py:5PASS +8unit tests; original/red and repeat/green saved |
| Review halfpage A3s/B.8s, admission, recovery, stream, lecture company primary | docs/review.md; suppliedvideo24:40 slide141; Microsoft Philly primaryATC2019 |
| Disk/limits before, bounded images/volumes/retention/actualsize, cleanup | preflight/host-before+limits+resources-after; README commands onlyownstand |
| Repo/commit, deps/images pinned, raw results, policies/export/report | requirements-runtime.lock/analysis.lock; preflight/images.json; report.html; docs/submission.md; final localcommit and gitlog |
| Fourplots units/conditions | results/plots/1-ready-rollout,2-per-pod,3-policies,4-hpa.png |
| Silent actualscreenvideo afterverification | videos/ MP4, results/video-review.json; OBS audio muted/no captions |

Первоначальные отрицательные проверки в checks-a.json не удалены. Они относятся к перегрузочному rollout и неэффективному kill из собственного PID namespace; окончательные доказательства — checks-a-repeat.json и kubernetes-checks.json. Фиксированный cold start до появления endpoints имеет ожидаемые сетевые ошибки; они сохранены и объяснены, а не скрыты.
