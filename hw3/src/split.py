"""Стадия split: разбиение на train/val/test по группам.

Почему не случайно по строкам. Случайный сплит рвёт группу пополам: задания
внутри одной темы — парафразы друг друга («напиши функцию сортировки списка»
в тридцати формулировках), и половина из них уезжает в train, половина в test.
Пайплайн зелёный, метрика на test завышена, симптомов нет. Замер с лекции:
случайный сплит — 19,5% утечки, по темам — 12,3%, дедупликация плюс группы — 0.

Поэтому здесь: неделимая единица — ГРУППА (split.group_key), а не строка.
И поэтому же стадия заканчивается проверкой контаминации, которая ПАДАЕТ:
сплит, который сам себя проверил и промолчал о находке, бесполезен.
"""

import json
import random
import time
from pathlib import Path

from src.config import load_params
from src.contamination import is_clean, report
from src.schema import Example, dump, iter_examples
from src.textnorm import normalize_group


def group_split(
    groups: dict[str, list[Example]], ratios: dict[str, float], seed: int
) -> dict[str, list[str]]:
    """Разложить ГРУППЫ по сплитам в заданных долях.

    Жадный алгоритм: группы идут от крупной к мелкой, каждая попадает туда,
    где сейчас наибольший недобор строк. Крупные первыми — иначе последняя
    большая группа некуда не помещается и доли разъезжаются.

    Перемешивание с seed нужно, чтобы порядок одинаковых по размеру групп
    не зависел от порядка строк в источнике: иначе v2 переставила бы
    половину тем между сплитами просто из-за нового шарда.
    """
    keys = sorted(groups)
    random.Random(seed).shuffle(keys)
    keys.sort(key=lambda k: len(groups[k]), reverse=True)

    total = sum(len(v) for v in groups.values())
    target = {name: total * share for name, share in ratios.items()}
    placed: dict[str, list[str]] = {name: [] for name in ratios}
    filled = {name: 0 for name in ratios}

    for key in keys:
        name = max(ratios, key=lambda n: target[n] - filled[n])
        placed[name].append(key)
        filled[name] += len(groups[key])

    empty = [name for name, keys_ in placed.items() if not keys_]
    if empty:
        raise SystemExit(
            f"сплит {empty} остался пустым: групп {len(groups)} на {len(ratios)} частей.\n"
            "Групповой сплит не может разрезать группу — нужно больше групп "
            "(diversity.min_groups) или другой split.group_key."
        )
    return placed


def main() -> None:
    params = load_params()
    paths = params["paths"]
    cfg = params["split"]
    started = time.perf_counter()

    examples: list[Example] = list(iter_examples(paths["clean"]))
    if cfg["group_key"] != "topic":
        raise SystemExit(f"неизвестный split.group_key: {cfg['group_key']!r}")

    groups: dict[str, list[Example]] = {}
    for ex in examples:
        groups.setdefault(normalize_group(ex.topic), []).append(ex)

    placed = group_split(groups, cfg["ratios"], cfg["seed"])
    buckets: dict[str, list[Example]] = {
        name: [ex for key in keys for ex in groups[key]] for name, keys in placed.items()
    }

    for name, rows in buckets.items():
        out = Path(paths[name])
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            for ex in rows:
                fh.write(dump(ex) + "\n")

    nd = params["clean"]["near_dup"]
    rep = report(
        buckets["train"],
        buckets["test"],
        shingle_words=nd["shingle_words"],
        num_perm=nd["num_perm"],
        threshold=params["contamination"]["threshold"],
    )

    metrics = {
        "version": params["collect"]["version"],
        "seed": cfg["seed"],
        "group_key": cfg["group_key"],
        "groups_total": len(groups),
        "sizes": {name: len(rows) for name, rows in buckets.items()},
        "groups": {name: len(keys) for name, keys in placed.items()},
        "ratios_actual": {
            name: round(len(rows) / len(examples), 4) for name, rows in buckets.items()
        },
        "contamination": rep,
        "seconds": round(time.perf_counter() - started, 2),
    }
    mpath = Path(paths["metrics_split"])
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        "split: "
        + ", ".join(f"{name} {len(rows)}" for name, rows in buckets.items())
        + f" (групп {len(groups)}, {metrics['seconds']} с)"
    )

    # Гейт, а не строчка в логе: утечка ничего не роняет сама по себе,
    # её единственный симптом — метрика, которая вас приятно удивила.
    if not is_clean(rep):
        raise SystemExit(
            "split: КОНТАМИНАЦИЯ train/test — "
            f"id {rep['id_overlap']}, текст {rep['text_overlap']}, "
            f"группы {rep['group_overlap']}, near-dup пар {rep['near_dup_pairs']}.\n"
            f"Примеры: {rep['examples']}\n"
            "Метрики на test завышены; сплит и чистку править обязательно."
        )


if __name__ == "__main__":
    main()
