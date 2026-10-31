# ДЗ 8–10. Исправление выпуска модели

Работа выполнена локально 1 ноября 2026 года. Исправлены семь независимых причин ошибок. Реализованы Prefect-flow и FastAPI с внедряемыми StubBackend/TransformersBackend. Настоящий кандидат отклонён; API обслуживает закреплённую baseline. Пороги качества не менялись.

## 1. Исходная версия, окружение, доказательства

Исходный прототип сохранён коммитом `867cb8f`. Исправленный код, новые тесты и доказательства находятся в следующем локальном коммите `hw8910`. Push не выполнялся; прежние ДЗ и их тесты не изменены. Приложенные `tests/test_release.py` сохранены без изменений.

Устройство: AMD Ryzen 7 7800X3D, Linux x86_64, Python 3.13.13. CUDA недоступна, генерация — CPU, bfloat16, 4 потока Torch. Лёгкое окружение отделено от тяжёлого; точные версии в `requirements-fast.lock` и `requirements-model-existing.lock`. Совместимость Prefect потребовала FastAPI 0.115.6, Starlette 0.41.3, SQLAlchemy 2.0.43. В тяжёлом существующем окружении FastAPI 0.142.2; реальный HTTP отдельно проверен там. Torch 2.14.0+cu130, Transformers 5.17.0, PEFT 0.21.0.

В [defects.csv](../defects.csv) — семь причин, сценарии и регрессионные тесты. [integration-before.log](evidence/integration-before.log) показывает падения всех семи первоначально добавленных интеграционных тестов на исходном прототипе. Это ошибки поведения, а не импорта или маршрутов. Три теста обращаются к настоящему HTTP-серверу, четыре запускают выпуск отдельными процессами. Восьмой дополнительный интеграционный тест проверяет сбой между pointer и journal; для него не заявляется красное доказательство на исходнике, где такого флага нет. Ещё пять safety-тестов проверяют диск, загрузку подменённых файлов, идентификаторы runtime/eval и schema подготовки.

В [local-ci-green.log](evidence/local-ci-green.log) — 13 публичных тестов и собственные тесты на обоих HTTP-адаптерах, всего 39 исполнений тестов. [contracts-before.log](evidence/contracts-before.log) отдельно сохраняет исходные ошибки контракта, включая неатомарную запись. Негативный CI: [local-ci-red.log](evidence/local-ci-red.log), exit 1 при намеренной поломке cache_key в отдельной копии. Рабочие файлы не ломались. После этого итоговый CI прошёл. Команды: `make check`, `make check-negative`.

## 2. Повторное использование ДЗ 6+7

Sweep не запускался, обучение не повторялось. Из прежней работы прочитаны:

- training run `3a65e960697647d3baaf701277157296`, registry `models:/my-qwen-adapter/2`;
- evaluation run `7ec864962e2140c1b387d1d3a55e7a59` и все исходные baseline/candidate outputs/eval;
- baseline `Qwen/Qwen3-0.6B`, commit `c1899de289a04d12100db370d81485cdf75e47ca`;
- 54 golden-примера, training-index, четыре behavioral-кейса, critical slice `code_output`;
- неизменённые scorer и quality_gate из `hw67-broken/evaluation/solution.py`.

Импорт адаптера из действительного MLflow: [mlflow-artifact.log](evidence/mlflow-artifact.log). Это чтение законченного run, не обучение. `scripts/fetch_candidate.py` проверяет соответствие registry version/run и FINISHED. Базовые веса уже находились в локальном HF snapshot; скачивать их повторно не потребовалось.

`previous_gate` заново подсчитал старые отчёты по сырым ответам и повторил исходный gate. Исторический отказ: behavioral 0/4. Затем выполнены полные реальные оценки в текущих условиях API, поскольку старые отчёты не содержат достаточного явного runtime binding. Сохранён и промежуточный опыт с tokenizer из адаптера; итоговая оценка использует одинаковые байты базового tokenizer для обеих моделей. Это не новая допущенная версия.

## 3. Prefect, подготовка и кеш

Граф: `prepare_input → obtain_artifact → evaluate_admission → publish_accepted`. Между задачами — небольшие URI, model ID, run ID и хеши. `obtain_artifact` читает уже полученный результат training run и пересчитывает файлы. Тензоры через результаты задач не передаются.

Подготовка реальных данных проверяет JSONL schema, непустой input, принадлежность expected к choices и отсутствие duplicate IDs. Результат сохраняется в `<workspace>/cache/<key>.json`; Prefect также сохраняет результат task и состояние в `.prefect/`. Ключ данных — SHA-256 канонического JSON с SHA байтов файла и всеми полями config: tokenizer revision/hash, template, max_length, code_revision. Пути и mtime не заменяют содержимое. Ключ task дополнительно включает workspace, чтобы URI результата не указывал в другой опыт.

[process-experiments.json](evidence/process-experiments.json) содержит все команды и exit codes. Сбой после подготовки — exit 1; следующий отдельный процесс — `Cached`, exit 0. Повтор — exit 0, без второго события. Изменение байтов по прежнему пути — `PREPARED`, task Completed, другой input digest. Логи: [process-failure.log](evidence/process-failure.log), [process-recovery.log](evidence/process-recovery.log), [process-invalidation.log](evidence/process-invalidation.log).

Этот же опыт выполнен с настоящим workspace: подготовка 54 golden-строк, управляемый сбой, Cached при повторе, чтение настоящего адаптера и отказ gate. См. [real-flow-experiments.json](evidence/real-flow-experiments.json), [real-flow-refusal.log](evidence/real-flow-refusal.log). Перед допуском также проверяется, что подготовленный golden совпадает с evaluated golden и не изменился после подготовки.

Повторы flow не включены для схемы, несовместимости и отказа качества. Сетевой импорт MLflow имеет timeout 10 с и максимум один retry; публикация работает с локальными проверенными файлами.

## 4. Атомарная публикация и восстановление

`validate_release` требует int schema=1, непустые IDs/URI, lowercase SHA-256, пересчитанный runtime hash, complete, настоящий boolean True, evaluation ID, привязку всех model/protocol/golden/runtime hashes, конечные числовые accuracy/format_rate в [0,1]. Missing, bool вместо метрики, NaN/Inf, чужой отчёт и отказ закрывают выпуск.

Перед публикацией и загрузкой отдельно пересчитываются реальные файлы по закреплённому inventory. Хеш модели — канонический словарь относительных имён и SHA файлов. Для кандидата inventory включает базу и adapter weights/config; использованный tokenizer и точная base revision закреплены. `publish` пишет временный файл рядом, flush/fsync, os.replace и fsync каталога. При ошибке replace старые байты сохраняются; временный файл очищается. Существующие пользовательские файлы не удалялись.

`release_id` учитывает весь manifest и связанное решение eval, включая runtime и evaluation run. Попытки отдельно записываются в attempts/flow-attempts; события выпуска — publications.jsonl. Перед pointer сохраняется durable pending intent; затем pointer; затем journal целиком заменяется атомарно, после чего pending помечается завершённым. При новом процессе незавершённое намерение доводится до согласованности. Сбой после pointer и повтор не создают двойное событие. Проверено в [process-pointer-recovery.log](evidence/process-pointer-recovery.log) и интеграционном тесте. Откат к прежнему принятому ID восстанавливает pointer; история не дублирует уже существующий выпуск.

Это решение рассчитано на одного писателя и локальную файловую систему. Оно не обеспечивает распределённую конкуренцию и не перезагружает API автоматически. Отказы running/foreign/rejected сохраняют побайтный pointer; SHA до/после записаны в process-experiments.json. Ошибка диска внесена через mock, настоящий диск не заполнялся.

## 5. Настоящий gate и manifest

[manifest-baseline.json](real/manifest-baseline.json), [manifest-candidate.json](real/manifest-candidate.json) фиксируют файлы, base revision, tokenizer, template, system, max_new_tokens=32, do_sample=False, seed=42, enable_thinking=False, dtype, device и версии генератора. Runtime SHA у итоговых оценок и API одинаковый: `f604d741130a0e8e146d381df2a852341117d517af6223da589a7c855e0841bd`.

Полные реальные отчёты и raw outputs находятся в `docs/real/*-runtime-{eval,outputs}.json`. Обвязка пересчитывает score по сырым ответам, проверяет output hash и соответствие model/runtime. Затем вызывает исходное правило допуска со всеми критическими срезами и behavioral; результат и SHA исходников помещает в [release-report.json](real/release-report.json). Перед flow правило вызывается снова; просто изменить passed недостаточно.

| Реальная модель | Golden n | Accuracy | Format rate | Behavioral | Ошибки генерации |
|---|---:|---:|---:|---:|---:|
| Baseline | 54 | 4/54 = 0,0741 | 9/54 = 0,1667 | 0/4 | 0 |
| Candidate | 54 | 3/54 = 0,0556 | 8/54 = 0,1481 | 0/4 | 0 |

Отказ: `Регрессия accuracy: 0.0556 < 0.0741`. Даже без этой регрессии behavioral не удовлетворяет правилу. Реальный flow завершился ненулевым кодом и сохранил SHA принятой baseline. Пороги не ослаблялись; `passed=true` вручную не выставлялся.

Baseline — исходная закреплённая версия из ДЗ 6+7 и fallback по условию задания. Она также имеет плохое качество и не объявляется новым quality PASS. Её начальный pointer создаётся отдельным bootstrap с явной политикой `existing-baseline-fallback`, происхождением и историческим отказом кандидата. Эту политику нельзя использовать для публикации нового кандидата. PASS синтетического стенда относится только к контрактам управления и не попадает в реальный gate.

## 6. API и фактическая версия

FastAPI использует lifespan и фоновую загрузку. Health отвечает за жизнь процесса; ready=503 и generate=503 до проверки файлов, загрузки модели и реального warmup. Ошибка загрузки оставляет ready=False. `/debug` — только диагностический localhost-маршрут.

Ограничения: prompt 1–8192 символа, вход с system/template не более 2048 токенов, только фиксированный оценённый лимит ответа 32. Пустой prompt, bool/строка/нулевой/чрезмерный лимит и неизвестные поля дают 4xx до вычислений. Генератор сериализован lock; HTTP-запросы могут ждать очередь.

[smoke.json](real/smoke.json) содержит health, ready, calls и реальный POST. На вопрос про `print(2 + 3)` получен `{"answer":"A"}`, 6 выходных токенов, model_id `baseline-Qwen3-0.6B-c1899de289a0`, runtime SHA, UUID и длительности. Слишком большой лимит вернул 400 и не увеличил calls. Это реальный Transformers на весах, не STUB.

[http-lifecycle.json](evidence/http-lifecycle.json) отдельно показывает STUB A → публикация B при работающем A → до restart ответ и ID всё ещё A → restart B → валидированный откат и restart A. Это подтверждает snapshot памяти и управляемую загрузку. Второй реально допущенной версии нет. Реальный API отдельно перезапущен на текущем accepted; [smoke-after-restart.json](real/smoke-after-restart.json) подтверждает загрузку той же baseline и runtime. Изменение accepted само по себе не меняет backend.

## 7. Нагрузка и объяснение

После warmup отправлены первые 8 golden-вопросов при concurrency=1 и ровно те же при concurrency=2. В обоих режимах max_new_tokens=32. Полный JSONL всех 16 попыток: [requests.jsonl](real/benchmark/requests.jsonl). Каждая строка хранит prompt/ID, статус, ошибку, client latency, compute/queue/total, actual model ID, runtime и output_tokens. Ошибки не фильтруются; в данном прогоне их нет.

| Concurrency | n | Успехи / ошибки | Пакет, с | Успешных req/s | Средняя / max latency успехов, с | Токены |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 8 | 8 / 0 | 3,329 | 2,403 | 0,416 / 0,440 | 55 |
| 2 | 8 | 8 / 0 | 3,273 | 2,444 | 0,773 / 0,859 | 55 |

Для ошибок latency отсутствует (null), а не искусственный ноль. Отдельные compute и queue показывают причину роста задержки: один backend продолжает вычислять последовательно, второй клиент ждёт lock. Удвоение HTTP concurrency не удваивает скорость генерации. На 8 запросах нельзя делать вывод об устойчивом p95; небольшое отличие throughput укладывается в шум такого опыта.

Измерена полная задержка единого JSON. TTFT и ITL не измерялись. Prefill обрабатывает весь prompt и строит attention-состояние; decode последовательно выдаёт новые токены с использованием KV-cache. Память KV-cache растёт с длиной контекста, количеством последовательностей, слоями/KV-heads и размером dtype. Приближённо K+V: `2 × layers × kv_heads × head_dim × cached_tokens × dtype_bytes` на последовательность. Последовательный Transformers с lock не использует механизмы continuous batching/paged KV-cache движков SGLang/vLLM; этот замер ничего не доказывает об их скорости.

## 8. Автоматизация, откат, сдача

Три триггера с конкретными командами — [triggers.md](triggers.md). Локальный CI выполнен; `ci.example.yml` — только необязательный шаблон. Удалённый Actions не запускался, merge не защищён настройками обязательной проверки.

Откат: выбрать ранее принятую согласованную пару manifest/report, повторно проверить gate/файлы, выполнить publish_event, перезапустить API, дождаться ready и проверить фактический model_id/runtime. Сохранить прежний accepted и доступ к весам до смены. Не редактировать ответ API и не подменять manifest случайной конфигурацией.

Одно шестиминутное видео с титрами собирает фактические сохранённые логи: `docs/video/homework8910.avi`. Это обзор доказательств, не live-запись; [сценарий](video-script.md) позволяет записать собственный показ. AVI и кадры не входят в Git, приложить отдельно. Никакой внешней публикации не выполнялось.

Артефакты для преподавателя: код и docs из Git; данные оценки через DVC предыдущего ДЗ; базовый публичный snapshot по точной revision; read-доступ к MLflow :5006 или отдельный экспорт модели/адаптера из run. Веса, .venv, кеши, volumes и секреты в сдачу/Git не включены. Абсолютные artifact/source URI относятся к текущей машине; копии отчётов в docs/real позволяют проверить их SHA, а команды восстанавливают рабочий каталог на другом компьютере.

Архитектурные справки: [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/), [Prefect caching](https://docs.prefect.io/v3/concepts/caching). Фактические результаты этой работы подтверждаются локальными файлами, а не ссылками на документацию.
