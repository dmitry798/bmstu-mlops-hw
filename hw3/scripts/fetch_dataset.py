#!/usr/bin/env python3
"""Скачать источник с HuggingFace и разложить на два шарда.

Источник: iamtarun/python_code_instructions_18k_alpaca — 18 612 строк,
одна таблица, только сплит train, лицензия источника указана в docs/datasheet.md.

Почему шарда два. Работа требует ДВЕ версии датасета, v1 и расширенную v2,
и разницу между ними через `dvc metrics diff`. Версия должна отличаться
СОСТАВОМ ДАННЫХ, а не параметром отсечки: подкрутить n_rows и объявить это
новой версией — самообман, стадия collect прочитала бы тот же самый файл.
Поэтому источник режется пополам: v1 — первый шард, v2 — оба.

Деление детерминированное и не по порядку строк: принадлежность шарду
определяется хэшем содержимого строки. Если резать «первая половина файла /
вторая», шарды получатся с разным составом тем (в источнике строки идут
не вперемешку), и разница v1 → v2 показывала бы не «данных стало больше»,
а «данные стали другими».

Скрипт не входит в пайплайн dvc: он готовит вход, а не артефакт. Запускается
один раз руками. Шарды лежат в data/source/ — под DVC, в git не попадают.

Запуск:  uv run python scripts/fetch_dataset.py
"""

import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

REPO = "iamtarun/python_code_instructions_18k_alpaca"
API = f"https://huggingface.co/api/datasets/{REPO}/tree/main?recursive=1"
RESOLVE = f"https://huggingface.co/datasets/{REPO}/resolve/main/"
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "source"
SHARDS = 2
COLUMNS = ("instruction", "input", "output")


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "mlops-hw3/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def parquet_paths() -> list[str]:
    """Имена parquet-файлов в репозитории датасета.

    Через API, а не хардкодом ссылки: имя файла в HF содержит хэш
    (train-00000-of-00001-<hash>.parquet) и меняется при перезаливке датасета.
    """
    tree = json.loads(http_get(API))
    paths = sorted(item["path"] for item in tree if item["path"].endswith(".parquet"))
    if not paths:
        raise SystemExit(f"в репозитории {REPO} не нашлось ни одного .parquet")
    return paths


def shard_of(row: dict) -> int:
    """Номер шарда по содержимому строки: воспроизводимо и без перекоса тем."""
    payload = "\x00".join(str(row.get(c) or "") for c in COLUMNS).encode("utf-8")
    return int(hashlib.sha1(payload).hexdigest(), 16) % SHARDS


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        names = parquet_paths()
        print(f"файлов в источнике: {len(names)}")
        tables = []
        for name in names:
            print(f"  скачиваю {name} …")
            raw = http_get(RESOLVE + name)
            tables.append(pq.read_table(pa.BufferReader(raw)))
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(
            f"не удалось скачать датасет: {exc}\n"
            f"Проверьте сеть или скачайте parquet вручную со страницы\n"
            f"  https://huggingface.co/datasets/{REPO}\n"
            f"и положите его в {OUT_DIR}."
        )

    table = pa.concat_tables(tables)
    missing = [c for c in COLUMNS if c not in table.column_names]
    if missing:
        raise SystemExit(f"в источнике нет колонок {missing}, есть {table.column_names}")

    rows = table.select(list(COLUMNS)).to_pylist()
    buckets: list[list[dict]] = [[] for _ in range(SHARDS)]
    for row in rows:
        buckets[shard_of(row)].append(row)

    for i, bucket in enumerate(buckets):
        out = OUT_DIR / f"{i:04d}.parquet"
        pq.write_table(pa.Table.from_pylist(bucket, schema=table.select(list(COLUMNS)).schema), out)
        print(f"  {out.relative_to(OUT_DIR.parents[1])}: {len(bucket)} строк")

    print(f"\nвсего строк: {len(rows)}. Дальше: uv run dvc repro")
    return 0


if __name__ == "__main__":
    sys.exit(main())
