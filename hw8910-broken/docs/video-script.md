# Сценарий одного видео: 6 минут

Видео собирается из фактических сохранённых результатов, с русскими титрами, без озвучки. Это обзор доказательств, а не запись нового live-запуска. Для записи собственным голосом можно пройти те же шаги в терминале.

| Время | Что показать | Команда / файл |
|---|---|---|
| 0:00–0:30 | Задача и исходный коммит | `git log --oneline -2`, README |
| 0:30–1:00 | Семь причин, до исправления | defects.csv, integration-before.log |
| 1:00–1:30 | Зелёный и намеренно красный CI | local-ci-green.log, local-ci-red.log |
| 1:30–2:00 | Отдельные задачи Prefect; descriptors | flow.py, process-failure.log |
| 2:00–2:30 | Восстановление из Cached, новая подготовка | process-recovery.log, process-invalidation.log |
| 2:30–3:00 | Отказы и SHA accepted | process-experiments.json |
| 3:00–3:30 | Один выпуск после сбоя pointer/journal | process-pointer-failure.log, process-pointer-recovery.log |
| 3:30–4:00 | STUB A → B → A, три перезапуска | test_http_loaded_version_restart_and_rollback, fastapi-after.log |
| 4:00–4:30 | Реальные веса, runtime, происхождение | docs/real/manifest-baseline.json, mlflow-artifact.log |
| 4:30–5:00 | Полный реальный gate и честный отказ | release-report.json, real-flow-experiments.json |
| 5:00–5:30 | Реальный API: готовность, ответ, 400 | docs/real/smoke.json |
| 5:30–6:00 | Нагрузка, очередь и ограничения | docs/real/benchmark/summary.csv, requests.jsonl |

Сборка: `../hw67-broken/.venv/bin/python scripts/build_video.py`.
Получится `docs/video/homework8910.avi` (MJPEG, 1600×900, 1 fps, 360 секунд).
Видео и его кадры не включаются в Git. Для сдачи приложить AVI отдельно или загрузить вручную и добавить ссылку. Публикация видео автоматически не выполняется.
