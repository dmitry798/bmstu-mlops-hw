"""Стадия collect: источник → data/raw.jsonl.

Источник — iamtarun/python_code_instructions_18k_alpaca: 18 612 строк формата
alpaca (instruction / input / output / prompt), одна таблица, только train.
Шарды готовит scripts/fetch_dataset.py, пути — в params.yaml → collect.sources.

Контракт стадии, а не её внутренности, держит остальной пайплайн: на выходе
JSONL со строками {"id", "topic", "messages": [system, user, assistant]}.

Скачанный чужой набор сам по себе сдачей не является. Поэтому стадия не
перекладывает parquet в JSONL один в один, а делает пять вещей, и каждая
видна числом в metrics/collect.json:

  1. размечает темой (src/topics.py) — в источнике поля темы нет вообще,
     а без него нечем делать ни групповой сплит, ни гейт разнообразия;
  2. сверяет ответ с реальностью (collect.verify_output_syntax): ответ здесь —
     код, и он обязан разбираться ast.parse. Обрезанные и битые примеры
     выбрасываются, а не переносятся в обучение;
  3. снимает markdown-обрамление ```python … ``` (collect.strip_code_fences),
     чтобы модель не заучила разметку как часть ответа;
  4. балансирует по темам (collect.max_per_topic), иначе крупнейшая тема
     решает за весь датасет;
  5. разводит единственную инструкцию источника на варианты
     (collect.system_prompts), чтобы модель не заучила её формулировку.
"""

import ast
import hashlib
import json
import time
import warnings
from collections import Counter
from pathlib import Path

import pyarrow.parquet as pq

from src.config import load_params, source_files
from src.topics import classify, clean_instruction, known_topics, unknown_labels

COLUMNS = ["instruction", "input", "output"]
BATCH = 2000
FENCE = "```"


def pick_prompt(example_id: str, variants: list[str]) -> str:
    """Детерминированно выбрать вариант инструкции по id примера.

    Именно sha1, а не встроенный hash(): тот солится на каждый запуск процесса,
    и raw.jsonl переставал бы быть воспроизводимым.
    """
    digest = hashlib.sha1(example_id.encode("utf-8")).hexdigest()
    return variants[int(digest, 16) % len(variants)]


def make_id(instruction: str, source_input: str, output: str) -> str:
    """Стабильный id из содержимого: в источнике поля id нет.

    От содержимого, а не от номера строки: иначе id поедут при смене версии
    (v2 добавляет второй шард), и train/test перестанут сравниваться между
    версиями, а dvc metrics diff показал бы шум вместо разницы.
    """
    payload = "\x00".join((instruction, source_input, output)).encode("utf-8")
    return "alpaca-" + hashlib.sha1(payload).hexdigest()[:16]


def strip_fences(code: str) -> tuple[str, bool]:
    """Снять markdown-обрамление вокруг кода. Возвращает код и признак «снято»."""
    text = code.strip()
    if not text.startswith(FENCE):
        return code.strip(), False
    lines = text.splitlines()
    lines = lines[1:]                      # ```python
    while lines and lines[-1].strip().startswith(FENCE):
        lines.pop()
    return "\n".join(lines).strip(), True


def is_python(code: str) -> bool:
    """Разбирается ли ответ как Python. Наша проверка чужой разметки.

    Аналог сверки с correct_choice_indices в курсовом примере: там ответ —
    номер варианта и его сверяют с разметкой источника, здесь ответ — код
    и его сверяют с грамматикой языка. Смысл тот же: не принимать чужую
    разметку на веру.
    """
    try:
        # Чужой код сплошь содержит '\d' в обычных строках вместо r'\d'.
        # ast.parse честно предупреждает об этом на каждой такой строке,
        # и лог стадии превращается в полсотни SyntaxWarning, за которыми
        # не видно собственных сообщений. Это замечание о стиле ИСХОДНИКА,
        # а не наша ошибка: гасим предупреждение, но не саму проверку —
        # SyntaxError ниже по-прежнему выбрасывает пример.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            ast.parse(code)
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        return False
    return True


def build_user(instruction: str, source_input: str) -> str:
    """Реплика пользователя: формулировка задачи плюс входные данные, если есть.

    Колонка input в источнике заполнена меньше чем у половины строк; когда она
    пуста, лишнего заголовка в промпте быть не должно — иначе модель выучит
    пустую секцию как обязательную часть формата.
    """
    text = instruction
    extra = (source_input or "").strip()
    if extra:
        text += "\n\nВходные данные:\n" + extra
    return text


def main() -> None:
    params = load_params()
    cfg = params["collect"]
    paths = params["paths"]
    n_rows = cfg["n_rows"]
    variants = cfg["system_prompts"]
    if not variants:
        raise SystemExit("collect.system_prompts пуст: инструкцию брать неоткуда")

    topics = cfg["topics"]
    wanted = set(topics) if topics else None
    if wanted:
        bad = unknown_labels(wanted)
        if bad:
            raise SystemExit(
                "collect.topics содержит темы, которых нет в таксономии "
                f"src/topics.py: {bad}\nДоступно тем: {len(known_topics())}"
            )

    out = Path(paths["raw"])
    out.parent.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    scanned = written = 0
    dropped_untagged = dropped_topic = dropped_syntax = 0
    dropped_short = dropped_dup_id = dropped_over_cap = 0
    fences_stripped = 0
    per_topic: Counter[str] = Counter()
    prompts_used: set[str] = set()
    seen_ids: set[str] = set()
    files = source_files(params)

    with out.open("w", encoding="utf-8") as fh:
        for src in files:
            taken = 0
            # Фильтры применяются ДО отсечки n_rows: иначе «первые N строк»
            # и «N строк по теме» — разные вещи, и сужение набора давало бы
            # случайный огрызок вместо заказанного объёма.
            for batch in pq.ParquetFile(src).iter_batches(batch_size=BATCH, columns=COLUMNS):
                if taken >= n_rows:
                    break
                for row in batch.to_pylist():
                    if taken >= n_rows:
                        break
                    scanned += 1

                    instruction = clean_instruction(row["instruction"])
                    source_input = (row["input"] or "").strip()
                    code, stripped = strip_fences(row["output"] or "")

                    if len(code.splitlines()) < cfg["min_output_lines"] or not instruction:
                        dropped_short += 1
                        continue
                    if cfg["verify_output_syntax"] and not is_python(code):
                        dropped_syntax += 1
                        continue

                    topic = classify(instruction, source_input, code)
                    if topic is None:
                        # Корзины «other» здесь нет сознательно: см. src/topics.py.
                        dropped_untagged += 1
                        continue
                    if wanted is not None and topic not in wanted:
                        dropped_topic += 1
                        continue
                    if per_topic[topic] >= cfg["max_per_topic"]:
                        dropped_over_cap += 1
                        continue

                    example_id = make_id(instruction, source_input, code)
                    if example_id in seen_ids:
                        # Побайтовый повтор внутри источника: v2 включает оба
                        # шарда, и повтор между ними иначе дошёл бы до clean.
                        dropped_dup_id += 1
                        continue
                    seen_ids.add(example_id)

                    prompt = pick_prompt(example_id, variants)
                    prompts_used.add(prompt)
                    record = {
                        "id": example_id,
                        "topic": topic,
                        "messages": [
                            {"role": "system", "content": prompt},
                            {"role": "user", "content": build_user(instruction, source_input)},
                            {"role": "assistant", "content": code},
                        ],
                    }
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                    per_topic[topic] += 1
                    fences_stripped += stripped
                    taken += 1
                    written += 1

    largest = per_topic.most_common(1)[0] if per_topic else ("", 0)
    metrics = {
        "version": cfg["version"],
        "files": len(files),
        "rows_scanned": scanned,
        "rows_written": written,
        "dropped_untagged": dropped_untagged,
        "dropped_topic_filter": dropped_topic,
        "dropped_answer_mismatch": dropped_syntax,
        "dropped_too_short": dropped_short,
        "dropped_duplicate_id": dropped_dup_id,
        "dropped_over_topic_cap": dropped_over_cap,
        "code_fences_stripped": fences_stripped,
        "topics_total_in_taxonomy": len(known_topics()),
        "topics_filter": len(wanted) if wanted else 0,
        "topics_kept": len(per_topic),
        "largest_topic": largest[0],
        "largest_topic_share": round(largest[1] / written, 4) if written else 0.0,
        "system_prompt_variants": len(prompts_used),
        "seconds": round(time.perf_counter() - started, 2),
    }
    mpath = Path(paths["metrics_collect"])
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"collect: версия {cfg['version']}, файлов {metrics['files']}, "
        f"просмотрено {scanned}, записано {written} "
        f"(без темы -{dropped_untagged}, фильтр тем -{dropped_topic}, "
        f"битый код -{dropped_syntax}, сверх лимита темы -{dropped_over_cap}), "
        f"тем {len(per_topic)}, вариантов инструкции {len(prompts_used)}, "
        f"{metrics['seconds']} с → {out}"
    )


if __name__ == "__main__":
    main()
