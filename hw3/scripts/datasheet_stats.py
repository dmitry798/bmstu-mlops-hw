#!/usr/bin/env python3
"""Числа для docs/datasheet.md: объём, темы, распределение длин.

Отдельный скрипт, а не копипаста из метрик руками: datasheet обязан
пересобираться после каждой смены версии данных, иначе он начинает описывать
датасет, которого больше нет. Вывод — готовый markdown, вставляется в разделы
«Объём», «Темы» и «Распределение длин».

Запуск:  uv run python scripts/datasheet_stats.py   (или make stats)
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import load_params  # noqa: E402
from src.schema import iter_examples  # noqa: E402
from src.stats import spread  # noqa: E402
from src.textnorm import normalize_group  # noqa: E402


def table(rows: list[tuple[str, object]]) -> str:
    return "\n".join(f"| {a} | {b} |" for a, b in rows)


def main() -> int:
    params = load_params()
    paths = params["paths"]
    version = params["collect"]["version"]

    examples = list(iter_examples(paths["clean"]))
    topics = Counter(normalize_group(ex.topic) for ex in examples)
    user_len = spread([len(ex.user) for ex in examples])
    asst_len = spread([len(ex.assistant) for ex in examples])
    lines = spread([len(ex.assistant.splitlines()) for ex in examples])

    sizes = {}
    for name in ("train", "val", "test"):
        p = Path(paths[name])
        sizes[name] = sum(1 for _ in p.open(encoding="utf-8")) if p.exists() else 0

    collect_metrics = {}
    mp = Path(paths["metrics_collect"])
    if mp.exists():
        collect_metrics = json.loads(mp.read_text(encoding="utf-8"))

    print(f"<!-- сгенерировано scripts/datasheet_stats.py, версия {version} -->\n")
    print("### Объём\n")
    print("| Показатель | Значение |")
    print("| --- | --- |")
    print(table([
        ("Версия", version),
        ("Просмотрено строк источника", collect_metrics.get("rows_scanned", "—")),
        ("Записано в raw.jsonl", collect_metrics.get("rows_written", "—")),
        ("После очистки (clean.jsonl)", len(examples)),
        ("train / val / test", f"{sizes['train']} / {sizes['val']} / {sizes['test']}"),
        ("Тем (групп)", len(topics)),
        ("Крупнейшая тема", f"{topics.most_common(1)[0][0]} — "
                            f"{topics.most_common(1)[0][1]} "
                            f"({topics.most_common(1)[0][1] / max(len(examples), 1):.1%})"),
    ]))

    print("\n### Распределение длин (символы, если не указано иное)\n")
    print("| Поле | p10 | p50 | p90 | min | max | p90/p10 |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for name, s in (("Задание (user)", user_len), ("Код (assistant)", asst_len),
                    ("Код, строк", lines)):
        print(f"| {name} | {s['p10']} | {s['p50']} | {s['p90']} | "
              f"{s['min']} | {s['max']} | {s['ratio_p90_p10']} |")

    print("\n### Темы: топ-15 и хвост\n")
    print("| Тема | Примеров | Доля |")
    print("| --- | --- | --- |")
    for label, n in topics.most_common(15):
        print(f"| {label} | {n} | {n / len(examples):.1%} |")
    print(f"\nВсего тем: {len(topics)}; "
          f"медианный размер темы: {sorted(topics.values())[len(topics) // 2]}; "
          f"минимальный: {min(topics.values())}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
