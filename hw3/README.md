# ДЗ 3 — Свой датасет + DVC: версии, валидация схемы, честный сплит

Датасет: **генерация Python-кода по текстовому описанию**.
Источник — [`iamtarun/python_code_instructions_18k_alpaca`](https://huggingface.co/datasets/iamtarun/python_code_instructions_18k_alpaca),
переработанный стадией `collect` (разметка темой, сверка кода `ast.parse`,
снятие markdown-обрамления, балансировка по темам, разведение инструкции
на варианты). Подробности и числа — в `docs/datasheet.md`.

## Запуск

```bash
uv sync
uv run python scripts/fetch_dataset.py   # или make fetch — скачать источник
make repro                               # весь пайплайн
make check                               # самопроверка, восемь пунктов
```

Остальные цели:

```bash
make v1 / make v2      # переключение версии датасета (и repro)
make diff              # dvc metrics diff
make diversity         # гейт разнообразия
make contamination     # гейт train/test
make stats             # числа для docs/datasheet.md
make dag               # граф пайплайна
```

Перед первым запуском нужен remote DVC (в репозитории уже настроен локальный
`../hw3-dvc-storage`); после прогона — `uv run dvc push`.

## Пайплайн

```
data/source/*.parquet
      │
   collect ──► data/raw.jsonl        + metrics/collect.json
      │
    clean ──► data/clean.jsonl       + metrics/clean.json
      │          схема → длины → ПДн → точная дедупликация → near-dup
      ├── diversity                  + metrics/diversity.json   (гейт, падает)
      │
    split ──► data/{train,val,test}.jsonl + metrics/split.json
                 групповой сплит по topic + гейт контаминации (падает)
```

Контракт между стадиями — `data/raw.jsonl`: строки вида
`{"id", "topic", "messages": [system, user, assistant]}`. Менять под свой
источник нужно только `collect`.

## Конфигурация

Всё — в `params.yaml`: версия датасета, пути, пороги очистки, пороги
разнообразия, доли и seed сплита. В коде нет ни одного пути и ни одного
порога строкой. Таксономия тем — в `src/topics.py`.

## Отчёты

- `docs/datasheet.md` — источник, лицензия, объём, распределение длин,
  что сделано с источником, известные ограничения;
- `docs/defects.md` — разбор пяти намеренных дефектов: в чём был,
  как проявлялся, как исправлен, каким числом подтверждается.

Данные в git не попадают ни при каких обстоятельствах — ни сейчас,
ни на девятой неделе, когда репозиторий соберёт CI.
