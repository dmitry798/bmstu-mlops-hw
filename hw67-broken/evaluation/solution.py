"""Реализуйте две функции. Контракт и примеры: EVALUATION.md и tests/test_eval.py."""
import json
import math

FIELDS = ('n', 'correct', 'valid', 'errors', 'accuracy', 'format_rate')


def parse(raw, choices):
    """Строгий разбор: JSON-объект ровно с одним полем answer, строкой из choices."""
    if not isinstance(raw, str):
        return None
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(value, dict) or set(value) != {'answer'}:
        return None
    answer = value['answer']
    return answer if isinstance(answer, str) and answer in choices else None


def summarize(items):
    n = len(items)
    correct = sum(i['correct'] for i in items)
    valid = sum(i['valid'] for i in items)
    errors = sum(i['error'] is not None for i in items)
    return dict(n=n, correct=correct, valid=valid, errors=errors,
                accuracy=correct / n if n else float('nan'),
                format_rate=valid / n if n else float('nan'))


def by_slice(per_item):
    names = sorted({s for item in per_item for s in item['slices']})
    return {name: summarize([i for i in per_item if name in i['slices']]) for name in names}


def score(rows, outputs):
    """Верните overall, slices и per_item. Не удаляйте плохие ответы из знаменателя.

    Строгий ответ: JSON с единственным строковым полем answer из choices.
    outputs: [{id, raw, error, latency_seconds}, ...].
    В overall и каждом срезе: n, correct, valid, errors, accuracy, format_rate.
    В per_item: id, raw, parsed, valid, correct, error, slices.
    Несовпадающие/дублирующиеся id и пустой набор должны вызвать ValueError.
    """
    if not rows:
        raise ValueError('Пустой набор заданий')
    row_ids = [r['id'] for r in rows]
    out_ids = [o['id'] for o in outputs]
    if len(row_ids) != len(set(row_ids)) or len(out_ids) != len(set(out_ids)):
        raise ValueError('Дублирующиеся id')
    if set(row_ids) != set(out_ids):
        raise ValueError('id заданий и ответов не совпадают')
    answers = {o['id']: o for o in outputs}
    per_item = []
    for row in rows:
        out = answers[row['id']]
        error = out.get('error')
        parsed = None if error is not None else parse(out.get('raw'), row['choices'])
        valid = parsed is not None
        per_item.append(dict(id=row['id'], raw=out.get('raw'), parsed=parsed, valid=valid,
                             correct=valid and parsed == row['expected'], error=error,
                             slices=list(row['slices'])))
    return dict(overall=summarize(per_item), slices=by_slice(per_item), per_item=per_item)


def check_report(report, role):
    """Отчёт полный, метрики конечны и совпадают с counts и per_item."""
    if not isinstance(report, dict) or report.get('status') != 'complete':
        raise ValueError(f'{role}: отчёт неполный')
    if not report.get('model'):
        raise ValueError(f'{role}: не указана модель')
    for key in ('overall', 'slices', 'per_item', 'behavioral'):
        if key not in report:
            raise ValueError(f'{role}: нет {key}')
    per_item = report['per_item']
    if not per_item:
        raise ValueError(f'{role}: пустой набор')
    ids = [i['id'] for i in per_item]
    if len(ids) != len(set(ids)):
        raise ValueError(f'{role}: дубли id')
    for item in per_item:
        if item['correct'] and not item['valid'] or item['valid'] and item['error'] is not None:
            raise ValueError(f'{role}: противоречивая строка {item["id"]}')
    check_metrics(report['overall'], summarize(per_item), f'{role}.overall')
    expected_slices = by_slice(per_item)
    if set(report['slices']) != set(expected_slices):
        raise ValueError(f'{role}: срезы не соответствуют per_item')
    for name, value in report['slices'].items():
        check_metrics(value, expected_slices[name], f'{role}.slices.{name}')
    check_counts(report['behavioral'].get('overall'), f'{role}.behavioral')


def check_counts(m, where):
    if not isinstance(m, dict) or any(k not in m for k in FIELDS):
        raise ValueError(f'{where}: нет метрик')
    if any(isinstance(m[k], bool) or not isinstance(m[k], (int, float)) or not math.isfinite(m[k]) for k in FIELDS):
        raise ValueError(f'{where}: метрика не конечна')
    n = m['n']
    if n <= 0 or not 0 <= m['correct'] <= m['valid'] <= n or not 0 <= m['errors'] <= n - m['valid']:
        raise ValueError(f'{where}: некорректные counts')
    if not math.isclose(m['accuracy'], m['correct'] / n) or not math.isclose(m['format_rate'], m['valid'] / n):
        raise ValueError(f'{where}: метрики не соответствуют counts')


def check_metrics(m, expected, where):
    check_counts(m, where)
    if any(m[k] != expected[k] for k in ('n', 'correct', 'valid', 'errors')):
        raise ValueError(f'{where}: counts не соответствуют per_item')


def quality_gate(baseline, candidate, critical_slices):
    """Верните {passed: True, ...} или вызовите ValueError с причиной отказа.

    Проверьте совместимость протокола/набора/baseline, метрики и counts,
    все id и срезы, общую accuracy/format_rate, критические срезы и behavior.
    Missing, NaN, пустой набор и ошибки генерации означают отказ.
    Пороги задаются до измерения; учебный допуск регрессии равен нулю.
    """
    for key in ('protocol_sha256', 'golden_sha256', 'baseline_spec_sha256'):
        if not baseline.get(key) or baseline.get(key) != candidate.get(key):
            raise ValueError(f'Несовместимые отчёты: {key}')
    check_report(baseline, 'baseline')
    check_report(candidate, 'candidate')
    a, b = baseline['overall'], candidate['overall']
    if a['n'] < 50:
        raise ValueError(f'Golden set: {a["n"]} < 50')
    if [i['id'] for i in baseline['per_item']] != [i['id'] for i in candidate['per_item']]:
        raise ValueError('Разные id в отчётах')
    if len(baseline['slices']) < 3:
        raise ValueError('Нужно минимум три среза')
    if set(baseline['slices']) != set(candidate['slices']) or any(
            baseline['slices'][s]['n'] != candidate['slices'][s]['n'] for s in baseline['slices']):
        raise ValueError('Разные срезы или размеры групп')
    if not critical_slices:
        raise ValueError('Не заданы критические срезы')
    if b['errors']:
        raise ValueError(f'Ошибки генерации кандидата: {b["errors"]}')
    if b['accuracy'] < a['accuracy']:
        raise ValueError(f'Регрессия accuracy: {b["accuracy"]:.4f} < {a["accuracy"]:.4f}')
    if b['format_rate'] < a['format_rate']:
        raise ValueError(f'Регрессия format_rate: {b["format_rate"]:.4f} < {a["format_rate"]:.4f}')
    for name in critical_slices:
        if name not in baseline['slices']:
            raise ValueError(f'Критический срез {name} отсутствует')
        sa, sb = baseline['slices'][name], candidate['slices'][name]
        if sb['accuracy'] < sa['accuracy']:
            raise ValueError(f'Регрессия в критическом срезе {name}: {sb["accuracy"]:.4f} < {sa["accuracy"]:.4f}')
    beh = candidate['behavioral']['overall']
    if beh['n'] < 3 or beh['errors'] or beh['correct'] != beh['n']:
        raise ValueError(f'Behavioral: прошли {beh["correct"]} из {beh["n"]}')
    return dict(passed=True, n=b['n'], critical_slices=list(critical_slices),
                baseline=dict(accuracy=a['accuracy'], format_rate=a['format_rate']),
                candidate=dict(accuracy=b['accuracy'], format_rate=b['format_rate']),
                behavioral=dict(correct=beh['correct'], n=beh['n']))
