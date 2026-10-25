"""Данные проверки ДЗ 6+7: golden, behavioral и полный индекс train.

Тема та же, что в ДЗ 3-4: программирование на Python. Train ДЗ 4 - это задачи
«напиши код», golden - вопросы с выбором варианта (что выведет код / понятие),
написанные вручную и проверенные запуском в интерпретаторе (см. --verify).

training-index строится из того же data/train.jsonl, что токенизировал ДЗ 4,
и сверяется по id с data/tokenized/train.pt: множества id обязаны совпасть.
"""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path

import torch

TRAIN_JSONL = Path('../hw4-broken/data/train.jsonl')
TRAIN_PT = Path('data/tokenized/train.pt')
OUT = Path('data/eval')
LABELS = ['A', 'B', 'C', 'D']
CHOICES = LABELS + ['REFUSE']

# (id, slices, вопрос, варианты A-D, верная метка, код для --verify или None)
GOLDEN = [
    # --- строки, что выведет код
    ('str-01', ['strings', 'code_output'], 'Что выведет print("abc"[::-1])?', ['abc', 'cba', 'bca', 'Ошибка'], 'B', 'print("abc"[::-1])'),
    ('str-02', ['strings', 'code_output'], 'Что выведет print("Hello".lower().count("l"))?', ['1', '0', '3', '2'], 'D', 'print("Hello".lower().count("l"))'),
    ('str-03', ['strings', 'code_output'], 'Что выведет print(len("  py  ".strip()))?', ['6', '4', '2', '0'], 'C', 'print(len("  py  ".strip()))'),
    ('str-04', ['strings', 'code_output'], 'Что выведет print("a,b,,c".split(","))?', ["['a', 'b', 'c']", "['a', 'b', '', 'c']", "['a,b,,c']", 'Ошибка'], 'B', 'print("a,b,,c".split(","))'),
    ('str-05', ['strings', 'code_output'], 'Что выведет print("-".join(["x", "y", "z"]))?', ['x-y-z', 'xyz', '-x-y-z-', "['x', 'y', 'z']"], 'A', 'print("-".join(["x", "y", "z"]))'),
    ('str-06', ['strings', 'code_output'], 'Что выведет print("Py" * 3)?', ['Py3', 'Ошибка TypeError', 'Py Py Py', 'PyPyPy'], 'D', 'print("Py" * 3)'),
    ('str-07', ['strings', 'code_output'], 'Что выведет print("python".capitalize())?', ['PYTHON', 'python', 'Python', 'pythoN'], 'C', 'print("python".capitalize())'),
    ('str-08', ['strings', 'code_output'], 'Что выведет print("abcdef"[1:4])?', ['abc', 'bcd', 'bcde', 'cde'], 'B', 'print("abcdef"[1:4])'),
    ('str-09', ['strings', 'code_output'], 'Что выведет print(f"{3.14159:.2f}")?', ['3.1', '3.142', '3.14159', '3.14'], 'D', 'print(f"{3.14159:.2f}")'),
    ('str-10', ['strings', 'code_output'], 'Что выведет print("banana".find("n"))?', ['2', '1', '3', '-1'], 'A', 'print("banana".find("n"))'),
    # --- коллекции, что выведет код
    ('col-01', ['collections', 'code_output'], 'Что выведет код: a = [1, 2, 3]; b = a; b.append(4); print(len(a))?', ['3', '4', 'Ошибка', '1'], 'B', 'a = [1, 2, 3]; b = a; b.append(4); print(len(a))'),
    ('col-02', ['collections', 'code_output'], 'Что выведет print([x * x for x in range(4)])?', ['[1, 4, 9, 16]', '[0, 1, 2, 3]', '[0, 1, 4, 9]', '[0, 2, 4, 6]'], 'C', 'print([x * x for x in range(4)])'),
    ('col-03', ['collections', 'code_output'], 'Что выведет код: d = {"a": 1}; print(d.get("b", 0))?', ['None', 'KeyError', '0', 'b'], 'C', 'd = {"a": 1}; print(d.get("b", 0))'),
    ('col-04', ['collections', 'code_output'], 'Что выведет print(sorted([3, 1, 2], reverse=True))?', ['[3, 2, 1]', '[1, 2, 3]', '[2, 1, 3]', 'None'], 'A', 'print(sorted([3, 1, 2], reverse=True))'),
    ('col-05', ['collections', 'code_output'], 'Что выведет print(len({1, 2, 2, 3, 3, 3}))?', ['6', '1', '0', '3'], 'D', 'print(len({1, 2, 2, 3, 3, 3}))'),
    ('col-06', ['collections', 'code_output'], 'Что выведет код: t = (1,); print(type(t).__name__)?', ['int', 'tuple', 'list', 'set'], 'B', 't = (1,); print(type(t).__name__)'),
    ('col-07', ['collections', 'code_output'], 'Что выведет print(list(zip([1, 2, 3], "ab")))?', ["[(1, 'a'), (2, 'b'), (3, None)]", 'Ошибка ValueError', "[(1, 'a'), (2, 'b')]", "[1, 'a', 2, 'b']"], 'C', 'print(list(zip([1, 2, 3], "ab")))'),
    ('col-08', ['collections', 'code_output'], 'Что выведет код: from collections import Counter; print(Counter("aab").most_common(1))?', ["[('a', 2)]", "[('b', 1)]", "{'a': 2}", "('a', 2)"], 'A', 'from collections import Counter; print(Counter("aab").most_common(1))'),
    ('col-09', ['collections', 'code_output'], 'Что выведет print([1, 2, 3][-1])?', ['1', 'Ошибка IndexError', '-1', '3'], 'D', 'print([1, 2, 3][-1])'),
    ('col-10', ['collections', 'code_output'], 'Что выведет код: d = {1: "a", 2: "b"}; print({v: k for k, v in d.items()}["b"])?', ['1', '2', 'b', 'KeyError'], 'B', 'd = {1: "a", 2: "b"}; print({v: k for k, v in d.items()}["b"])'),
    # --- управление и функции, что выведет код
    ('flow-01', ['control_flow', 'code_output'], 'Что выведет код: def f(x, y=2): return x * y; затем print(f(3))?', ['5', '9', '6', 'Ошибка'], 'C', 'def f(x, y=2): return x * y\nprint(f(3))'),
    ('flow-02', ['control_flow', 'code_output'], 'Что выведет print(sum(range(5)))?', ['15', '10', '5', '4'], 'B', 'print(sum(range(5)))'),
    ('flow-03', ['control_flow', 'code_output'], 'Что выведет код: i = 0; while i < 3: i += 1; после цикла print(i)?', ['0', '2', '4', '3'], 'D', 'i = 0\nwhile i < 3:\n    i += 1\nprint(i)'),
    ('flow-04', ['control_flow', 'code_output'], 'Что выведет print(list(map(lambda x: x + 1, [1, 2])))?', ['[2, 3]', '[1, 2]', '[1, 2, 1]', '<map object>'], 'A', 'print(list(map(lambda x: x + 1, [1, 2])))'),
    ('flow-05', ['control_flow', 'code_output'], 'Что выведет код: def g(*args): return len(args); затем print(g(1, 2, 3))?', ['1', '6', '3', 'Ошибка'], 'C', 'def g(*args): return len(args)\nprint(g(1, 2, 3))'),
    ('flow-06', ['control_flow', 'code_output'], 'Что выведет код: for i in range(3): pass; после цикла print(i)?', ['3', '2', '0', 'NameError'], 'B', 'for i in range(3):\n    pass\nprint(i)'),
    ('flow-07', ['control_flow', 'code_output'], 'Что выведет print(bool([]))?', ['False', 'True', 'None', '[]'], 'A', 'print(bool([]))'),
    ('flow-08', ['control_flow', 'code_output'], 'Что выведет код: x = 5; print("big" if x > 3 else "small")?', ['small', 'True', 'Ошибка', 'big'], 'D', 'x = 5; print("big" if x > 3 else "small")'),
    ('flow-09', ['control_flow', 'code_output'], 'Что выведет код: def h(): return; затем print(h())?', ['0', 'Ошибка', 'None', 'Пустую строку'], 'C', 'def h(): return\nprint(h())'),
    ('flow-10', ['control_flow', 'code_output'], 'Что выведет print(7 // 2, 7 % 2)?', ['3.5 1', '3 1', '3 0', '4 1'], 'B', 'print(7 // 2, 7 % 2)'),
    # --- типы и исключения, что выведет код
    ('err-01', ['errors_types', 'code_output'], 'Что выведет print(type(3 / 2).__name__)?', ['float', 'int', 'decimal', 'fraction'], 'A', 'print(type(3 / 2).__name__)'),
    ('err-02', ['errors_types', 'code_output'], 'Что выведет код: try: int("x") except ValueError: print("V") except TypeError: print("T")?', ['T', 'V', 'V и T', 'Ничего'], 'B', 'try:\n    int("x")\nexcept ValueError:\n    print("V")\nexcept TypeError:\n    print("T")'),
    ('err-03', ['errors_types', 'code_output'], 'Что выведет print(0.1 + 0.2 == 0.3)?', ['True', 'Ошибка', 'False', 'None'], 'C', 'print(0.1 + 0.2 == 0.3)'),
    ('err-04', ['errors_types', 'code_output'], 'Что выведет print(int("10", 2))?', ['10', '20', 'Ошибка', '2'], 'D', 'print(int("10", 2))'),
    ('err-05', ['errors_types', 'code_output'], 'Что выведет код: try: [][0] except IndexError: print("I") finally: print("F")?', ['I, затем F', 'Только I', 'Только F', 'Ошибка IndexError'], 'A', 'try:\n    [][0]\nexcept IndexError:\n    print("I")\nfinally:\n    print("F")'),
    ('err-06', ['errors_types', 'code_output'], 'Что выведет print(2 ** 3 ** 2)?', ['64', '512', '81', '36'], 'B', 'print(2 ** 3 ** 2)'),
    ('err-07', ['errors_types', 'code_output'], 'Что выведет print(round(2.5))?', ['3', '2.5', '2', '2.0'], 'C', 'print(round(2.5))'),
    ('err-08', ['errors_types', 'code_output'], 'Что выведет print(isinstance(True, int))?', ['True', 'False', 'Ошибка', 'None'], 'A', 'print(isinstance(True, int))'),
    # --- понятия
    ('con-01', ['strings', 'concept'], 'Какой метод строки проверяет, что она состоит только из цифр?', ['isalpha()', 'isdigit()', 'isspace()', 'islower()'], 'B', None),
    ('con-02', ['strings', 'concept'], 'Какое утверждение о строках str в Python верно?', ['Их можно менять по индексу: s[0] = "x"', 'Метод replace меняет строку на месте', 'У них нет метода split', 'Они неизменяемы: методы возвращают новую строку'], 'D', None),
    ('con-03', ['collections', 'concept'], 'Какая встроенная структура даёт проверку x in коллекция в среднем за O(1)?', ['list', 'tuple', 'set', 'str'], 'C', None),
    ('con-04', ['collections', 'concept'], 'Чем кортеж tuple отличается от списка list?', ['Кортеж неизменяем', 'Кортеж хранит только числа', 'Кортеж всегда отсортирован', 'Кортеж не поддерживает индексацию'], 'A', None),
    ('con-05', ['collections', 'concept'], 'Что делает dict.setdefault(k, v)?', ['Всегда перезаписывает значение по ключу k', 'Удаляет ключ k', 'Возвращает список ключей', 'Возвращает значение по k, а если ключа нет - вставляет v и возвращает его'], 'D', None),
    ('con-06', ['control_flow', 'concept'], 'Что делает оператор continue внутри цикла?', ['Завершает цикл', 'Переходит к следующей итерации', 'Повторяет текущую итерацию', 'Завершает функцию'], 'B', None),
    ('con-07', ['control_flow', 'concept'], 'Чем опасно объявление def f(x, acc=[])?', ['Это синтаксическая ошибка', 'acc всегда будет None', 'Список по умолчанию создаётся один раз и общий для всех вызовов', 'Функцию нельзя вызвать без acc'], 'C', None),
    ('con-08', ['control_flow', 'concept'], 'Что возвращает вызов функции, в теле которой есть yield?', ['Объект-генератор', 'Первое значение yield', 'Список всех значений', 'None'], 'A', None),
    ('con-09', ['errors_types', 'concept'], 'Какое исключение возникает при d["k"], если ключа "k" нет в словаре d?', ['IndexError', 'ValueError', 'AttributeError', 'KeyError'], 'D', None),
    ('con-10', ['errors_types', 'concept'], 'Когда выполняется блок finally в конструкции try?', ['Только если исключения не было', 'Всегда, было исключение или нет', 'Только если было исключение', 'Только при вызове sys.exit()'], 'B', None),
    ('con-11', ['errors_types', 'concept'], 'Какой оператор выполняет целочисленное деление с округлением вниз?', ['/', '%', '//', '**'], 'C', None),
    ('con-12', ['control_flow', 'concept'], 'Когда выполняется блок else у цикла for?', ['Если цикл завершился без break', 'Если был break', 'Перед первой итерацией', 'Никогда, это ошибка синтаксиса'], 'A', None),
    ('con-13', ['collections', 'concept'], 'Что возвращает метод list.sort()?', ['Новый отсортированный список', 'Исходный список', 'Число элементов', 'None, список сортируется на месте'], 'D', None),
    ('con-14', ['strings', 'concept'], 'Как получить число символов строки s?', ['s.length()', 'len(s)', 's.size', 'count(s)'], 'B', None),
    ('con-15', ['control_flow', 'concept'], 'Что такое args в объявлении def f(*args)?', ['Словарь именованных аргументов', 'Список, который можно менять', 'Кортеж дополнительных позиционных аргументов', 'Первый аргумент функции'], 'C', None),
    ('con-16', ['errors_types', 'concept'], 'Какой из встроенных типов неизменяемый?', ['list', 'dict', 'set', 'frozenset'], 'D', None),
]

BEHAVIORAL = [
    ('beh-format', 'format', 'beh-len', 'Ответь строго JSON без пояснений и без markdown. Что выведет print(len([0] * 3))?', ['0', '3', '1', '[0, 0, 0]'], 'B'),
    ('beh-para-1', 'paraphrase', 'beh-upper', 'Что напечатает print("ab".upper())?', ['ab', 'AB', 'Ab', 'Ошибка'], 'B'),
    ('beh-para-2', 'paraphrase', 'beh-upper', 'Какой результат вывода у выражения print("ab".upper())? Варианты переставлены.', ['AB', 'Ab', 'Ошибка', 'ab'], 'A'),
    ('beh-refusal', 'refusal', 'beh-out-of-domain', 'Какой город является столицей Франции?', ['Рим', 'Париж', 'Мадрид', 'Берлин'], 'REFUSE'),
]


def render(question, options):
    lines = [question] + [f'{label}) {text}' for label, text in zip(LABELS, options)]
    return '\n'.join(lines + ['choices: ' + ', '.join(CHOICES)])


def verify():
    """Каждый code_output-вопрос: эталонный вариант совпадает с реальным выводом."""
    for qid, _, _, options, expected, code in GOLDEN:
        if code is None:
            continue
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            exec(code, {})
        got = buf.getvalue().strip()
        want = options[LABELS.index(expected)]
        ok = got == want or (qid == 'err-05' and got == 'I\nF')
        print('OK ' if ok else 'BAD', qid, repr(got), '<->', repr(want))
        if not ok:
            raise SystemExit(f'{qid}: эталон не совпал с выводом интерпретатора')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify', action='store_true')
    if ap.parse_args().verify:
        verify()
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / 'golden.jsonl').open('w') as f:
        for qid, slices, question, options, expected, code in GOLDEN:
            f.write(json.dumps(dict(id=qid, group_id=f'golden-{qid}', input=render(question, options),
                expected=expected, choices=CHOICES, slices=slices,
                source='Написан вручную; ' + ('эталон проверен запуском кода в CPython 3.12' if code
                        else 'эталон по документации docs.python.org')), ensure_ascii=False) + '\n')
    with (OUT / 'behavioral.jsonl').open('w') as f:
        for qid, kind, group, question, options, expected in BEHAVIORAL:
            f.write(json.dumps(dict(id=qid, group_id=group, input=render(question, options), expected=expected,
                choices=CHOICES, slices=['behavior'], type=kind,
                source='Behavioral-кейс; REFUSE задан system-инструкцией evaluation/params.json'
                       if kind == 'refusal' else 'Behavioral-кейс, эталон проверен вручную'), ensure_ascii=False) + '\n')
    train = [json.loads(line) for line in TRAIN_JSONL.read_text().splitlines() if line.strip()]
    with (OUT / 'training-index.jsonl').open('w') as f:
        for row in train:
            user = next(m['content'] for m in row['messages'] if m['role'] == 'user')
            f.write(json.dumps(dict(id=row['id'], group_id=row['id'], input=user, topic=row['topic']),
                               ensure_ascii=False) + '\n')
    tensor_ids = [e['id'] for e in torch.load(TRAIN_PT, weights_only=True)['examples']]
    if sorted(tensor_ids) != sorted(r['id'] for r in train):
        raise SystemExit('training-index не совпадает по id с data/tokenized/train.pt')
    proof = dict(train_jsonl=str(TRAIN_JSONL), train_jsonl_sha256=sha(TRAIN_JSONL),
                 train_pt_sha256=sha(TRAIN_PT), n_train_index=len(train), n_train_pt=len(tensor_ids),
                 ids_equal=True)
    (OUT / 'training-index-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
