# ДЗ 8–10: исправленный выпуск и API

Исходный прототип: локальный коммит `867cb8f`. Исправленная версия — следующий коммит с префиксом `hw8910`. Git push не выполнялся. Предыдущие ДЗ и их tests не изменялись. Главный отчёт: [docs/report.md](docs/report.md); причины: [defects.csv](defects.csv).

## Быстрая проверка без весов

Python 3.13.13 (приложенные контракты совместимы с Python 3.12). Отдельное окружение:

```bash
cd hw8910-broken
uv venv .venv --python 3.13
uv pip install --python .venv/bin/python -r requirements-fast.lock
make check                    # 13 публичных + собственные, stdlib и FastAPI
make check-negative           # ОЖИДАЕТСЯ exit 1, ломается только отдельная копия
make check                    # исходный рабочий код остаётся зелёным
```

`requirements-fast.lock` закрепляет все пакеты реально проверенного лёгкого окружения. `requirements-model-existing.lock` описывает использованное тяжёлое окружение ДЗ 6+7; `requirements-model.txt` — основные зависимости для нового. Для стандартного прототипа достаточно `python3 -m unittest discover -s tests -v` и `python3 -m unittest discover -s integration_tests -v` (из этой папки). Полный `make check` включает FastAPI, но веса не загружает.

## Prefect и STUB-стенд

```bash
.venv/bin/python lab.py --workspace .lab-demo init
.venv/bin/python flow.py --workspace .lab-demo --fail-after-prepare # exit 1
.venv/bin/python flow.py --workspace .lab-demo                      # Cached
.venv/bin/python flow.py --workspace .lab-demo                      # без дубля события
.venv/bin/python service.py --framework fastapi --workspace .lab-demo --warmup-seconds 2
# /health, /ready, /debug и POST /generate {"prompt":"hello","max_new_tokens":32}
make prove-process # новый workspace; все команды/exit/SHA — docs/evidence/
```

Порт по умолчанию 8091, bind только 127.0.0.1. Для адаптера стандартной библиотеки опустите `--framework fastapi`. Тесты переключаются через `SERVICE_FRAMEWORK=fastapi`. STUB ONLY обозначает проверку управления, а не ответ модели.

Prefect работает локально; SQLite и persisted results в `.prefect/`, подготовленные результаты также в `<workspace>/cache/`. Ключ Prefect включает workspace и content/config digest; ключ данных не зависит от пути. В конфиге реального workspace зафиксированы точная ревизия токенизатора, его хеш, шаблон, длина и хеш кода подготовки. Внутри `prepare` проверяется schema golden JSONL; cache hit не выдаётся для изменённого входа. Между задачами передаются URI/ID/хеши, не веса.

## Реальная baseline и существующий адаптер

Уже выполнены реальные оценки 54+4 примеров и benchmark 8+8. Кандидат не принят; baseline обслуживается как ранее закреплённый fallback, не как новый PASS. Даже baseline не прошла behavioral — качество не скрывается.

Веса базы читаются из HF cache с точной ревизией, адаптер — из существующего MLflow run. Нового sweep/обучения нет. На этой машине тяжёлое окружение уже есть в `../hw67-broken/.venv`:

```bash
# Из корня репозитория: если локальный MLflow остановлен
# docker compose -p mlops-hw6 -f hw67-broken/compose.yaml up -d --no-build --wait
# Далее из hw8910-broken:
make real-init     # ОДИН РАЗ; существующий .real не перезаписывается
../hw67-broken/.venv/bin/python scripts/fetch_candidate.py
make candidate-init
make real-eval
make candidate-eval
make real-gate     # честный отказ, ОЖИДАЕТСЯ exit 1
make real-flow     # Prefect также отказывает, accepted не меняется
make serve-real    # baseline, FastAPI, CPU bfloat16, 4 torch threads
# В другом терминале:
.venv/bin/python scripts/real_smoke.py
make benchmark     # 8 запросов при c=1 и те же 8 при c=2
```

`real_release.py init --workspace OTHER --snapshot /path/to/<exact-revision>` позволяет использовать другой каталог. `init` никогда не стирает существующий workspace. Для переоценки используйте существующий workspace с теми же весами. API не скачивает веса: `local_files_only=True`, хеши пересчитываются при старте. Для смены версии нужен останов/перезапуск; изменение accepted не меняет объект в памяти.

API разрешает только оценённый лимит 32, без произвольных per-request настроек. Prompt — 1–8192 символа, токенизированный вход — до 2048 токенов вместе с system/template. Генератор один; конкурентные HTTP-запросы ждут lock. Ответ включает фактический ID, runtime hash, UUID, токены, compute/queue/total seconds. `/debug` — только локальная диагностика стенда.

## Доказательства и сдача

- `docs/evidence/`: красные/зелёные тесты, Prefect состояния, отказы, SHA, MLflow import.
- `docs/real/`: manifest без весов, полный eval и raw outputs, release-report, smoke и benchmark.
- `docs/triggers.md`: код/данные/адаптер → конкретные действия.
- `docs/video/`: локальное видео по сохранённым доказательствам (исключено из Git).
- `docs/video-script.md`: сценарий 6-минутного показа и команды.

Никаких весов, окружений, кешей и секретов в Git/архиве. Преподавателю нужны файлы проекта, данные оценки через DVC предыдущего ДЗ, общедоступная база `Qwen/Qwen3-0.6B` на закреплённом commit и read-доступ к локальному MLflow `:5006`/экспорт адаптера отдельно. Локальные абсолютные URI в manifest относятся к этой машине; перенос на другую — пересборка manifest с повторной проверкой файлов и eval при изменении runtime.

`ci.example.yml` — только шаблон. Удалённый Actions и защита merge не заявлены. Push для завершения работы не требуется.
