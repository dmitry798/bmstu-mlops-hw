"""Таксономия тем: превращает пару (задание, код) в ключ группы.

Зачем это вообще нужно. В источнике iamtarun/python_code_instructions_18k_alpaca
колонки ровно четыре: instruction, input, output, prompt. Поля «тема» нет —
а без него нечем делать ни групповой сплит, ни гейт разнообразия.

Почему нельзя обойтись без темы. Внутри источника задания массово повторяются
по смыслу: «напиши функцию, сортирующую список», «отсортируй список чисел по
возрастанию», «реализуй сортировку массива» — это десятки строк-парафразов.
Случайный сплит раскладывает такие парафразы по разные стороны train/test,
и метрика на test оказывается завышенной. Лекционный замер: случайный сплит —
19,5% утечки, сплит по группам после дедупликации — 0. Тема здесь и есть
та самая группа.

Как устроено. Упорядоченный список правил; строка получает ЛЕЙБЛ ПЕРВОГО
сработавшего правила. Порядок неслучаен: сначала узкие алгоритмические задачи
(«ханойские башни»), потом библиотеки (pandas, flask), потом конструкции языка
(декораторы, генераторы), потом широкие домены (веб, ML). Обратный порядок
схлопнул бы всё в «работа со списками».

Строка, не попавшая ни под одно правило, НЕ получает тему: см.
collect.drop_untagged в params.yaml. Корзины «other» здесь нет сознательно —
она была бы крупнейшей группой и обесценила бы и max_group_share, и сплит.
"""

import re
from typing import Iterable

# (лейбл темы, ключевые слова). Ключевое слово ищется как подстрока
# в нижнем регистре по тексту «задание + входные данные + код».
RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    # --- узкие классические задачи ---
    ("Ханойские башни", ("tower of hanoi", "hanoi")),
    ("Числа Фибоначчи", ("fibonacci", "fibonnaci")),
    ("Факториал", ("factorial",)),
    ("Простые числа", ("prime number", "is_prime", "isprime", "prime numbers", "sieve of eratosthenes")),
    ("Палиндромы", ("palindrome",)),
    ("Анаграммы", ("anagram",)),
    ("FizzBuzz", ("fizzbuzz", "fizz buzz")),
    ("НОД и НОК", ("greatest common divisor", "gcd(", "least common multiple", "lcm(")),
    ("Шифр Цезаря и простые шифры", ("caesar cipher", "vigenere", "rot13")),
    ("Проверка на високосный год", ("leap year",)),
    ("Задача о рюкзаке", ("knapsack",)),
    ("Задача коммивояжёра", ("travelling salesman", "traveling salesman")),
    ("N ферзей", ("n-queens", "n queens", "eight queens")),
    ("Числа Армстронга и совершенные числа", ("armstrong number", "perfect number")),
    ("Треугольник Паскаля", ("pascal's triangle", "pascals triangle")),
    ("Римские числа", ("roman numeral",)),
    ("Задача о сдаче монетами", ("coin change", "make change")),

    # --- алгоритмы ---
    ("Сортировка пузырьком", ("bubble sort",)),
    ("Быстрая сортировка", ("quick sort", "quicksort")),
    ("Сортировка слиянием", ("merge sort", "mergesort")),
    ("Сортировка вставками и выбором", ("insertion sort", "selection sort", "heap sort", "heapsort")),
    ("Сортировка (общая)", ("sort the list", "sort a list", "sort an array", "sorted(", ".sort(", "sorting algorithm")),
    ("Бинарный поиск", ("binary search",)),
    ("Линейный поиск", ("linear search", "search for an element", "search an element")),
    ("Динамическое программирование", ("dynamic programming", "memoization", "memoize", "longest common subsequence", "edit distance", "longest increasing subsequence")),
    ("Рекурсия", ("recursion", "recursive", "recursively")),
    ("Жадные алгоритмы и оптимизация", ("greedy", "optimal solution", "minimize the cost", "maximize the profit")),
    ("Сложность алгоритмов", ("time complexity", "big o", "space complexity")),

    # --- структуры данных ---
    ("Связный список", ("linked list",)),
    ("Стек", ("stack class", "implement a stack", "push and pop", "lifo")),
    ("Очередь", ("implement a queue", "queue class", "fifo", "deque")),
    ("Бинарное дерево", ("binary tree", "binary search tree", "bst", "tree traversal", "inorder", "preorder", "postorder")),
    ("Кучи и приоритетные очереди", ("heapq", "priority queue", "min heap", "max heap")),
    ("Графы", ("graph", "adjacency", "breadth-first", "depth-first", "bfs", "dfs", "dijkstra", "shortest path")),
    ("Хеш-таблицы", ("hash table", "hash map", "hashmap")),
    ("Матрицы", ("matrix", "2d array", "two-dimensional array", "transpose")),
    ("Множества", ("set()", "intersection of", "union of two", " sets ")),
    ("Кортежи", ("tuple",)),
    ("Словари", ("dictionary", "dictionaries", "dict(", "key-value")),
    ("Списки: фильтрация и агрегация", ("list of numbers", "sum of the list", "average of", "largest number", "smallest number", "maximum value", "minimum value")),
    ("Удаление дубликатов", ("remove duplicates", "duplicate elements", "unique elements")),

    # --- строки и текст ---
    ("Регулярные выражения", ("regular expression", "regex", "import re", "re.match", "re.sub", "re.findall")),
    ("Обработка строк", ("reverse the string", "reverse a string", "uppercase", "lowercase", "capitalize", "substring", "concatenate")),
    ("Подсчёт слов и символов", ("word count", "count the number of words", "count the occurrences", "frequency of each", "count vowels", "vowels in")),
    ("Валидация ввода", ("validate", "validation", "is valid", "check if the email", "password strength")),
    ("Обработка естественного языка", ("nltk", "spacy", "tokenize", "stop words", "stemming", "lemmat", "sentiment analysis")),

    # --- библиотеки и экосистема ---
    ("NumPy", ("numpy", "np.array", "import numpy")),
    ("Pandas", ("pandas", "dataframe", "pd.read", "import pandas")),
    ("Matplotlib и визуализация", ("matplotlib", "pyplot", "seaborn", "plot the", "bar chart", "histogram", "scatter plot")),
    ("scikit-learn", ("sklearn", "scikit-learn", "train_test_split", "randomforest", "logisticregression", "kmeans", "linear regression model")),
    ("Нейросети: TensorFlow и Keras", ("tensorflow", "keras", "tf.")),
    ("Нейросети: PyTorch", ("pytorch", "torch.nn", "import torch")),
    ("Машинное обучение (общее)", ("machine learning", "neural network", "training data", "classifier", "predict the", "model.fit", "accuracy score")),
    ("Flask и веб-приложения", ("flask", "@app.route", "render_template")),
    ("Django", ("django", "models.model")),
    ("HTTP-запросы и API", ("requests.get", "requests.post", "import requests", "rest api", "api endpoint", "http request")),
    ("Веб-скрапинг", ("beautifulsoup", "bs4", "scrape", "scraping", "html parser", "selenium")),
    ("Базы данных и SQL", ("sqlite", "sql query", "mysql", "postgres", "cursor.execute", "sqlalchemy", "database table")),
    ("JSON", ("json.loads", "json.dumps", "import json", "json file", "json object")),
    ("CSV и табличные файлы", ("csv.reader", "csv.writer", "import csv", "csv file")),
    ("Работа с файлами", ("open(", "read the file", "write to a file", "file path", "os.path", "with open")),
    ("Дата и время", ("datetime", "timestamp", "time.time", "strftime", "calendar module")),
    ("Случайные числа и генерация", ("random.", "import random", "random number", "password generator", "shuffle")),
    ("Математические вычисления", ("import math", "math.sqrt", "calculate the area", "quadratic equation", "compound interest", "square root")),
    ("Статистика", ("mean", "median", "standard deviation", "variance", "statistics module", "probability")),
    ("Конвертеры единиц", ("celsius", "fahrenheit", "convert kilometers", "convert the temperature", "currency conversion", "binary to decimal", "decimal to binary")),
    ("itertools и collections", ("itertools", "collections.", "counter(", "defaultdict", "namedtuple")),
    ("Многопоточность и async", ("threading", "multiprocessing", "asyncio", "async def", "concurrent")),
    ("Сетевое программирование", ("socket", "tcp", "udp", "server and client")),
    ("Графический интерфейс", ("tkinter", "pyqt", "gui application")),
    ("Командная строка и argparse", ("argparse", "sys.argv", "command line", "command-line")),
    ("Логирование", ("logging.", "import logging", "log messages")),
    ("Тестирование", ("unittest", "pytest", "assert ", "test case", "testcase")),
    ("Сериализация и хеширование", ("pickle", "hashlib", "md5", "sha256", "base64", "encrypt", "decrypt")),
    ("Электронная почта", ("smtplib", "send an email", "email message")),
    ("Обработка изображений", ("opencv", "cv2", "pillow", "from pil", "image file")),
    ("Игры", ("tic-tac-toe", "tic tac toe", "hangman", "rock paper scissors", "guessing game", "pygame", "snake game")),
    ("Чат-боты", ("chatbot", "chat bot", "dialogflow")),

    # --- конструкции языка ---
    ("Классы и ООП", ("class ", "__init__", "object-oriented", "inheritance", "subclass", "method of the class")),
    ("Декораторы", ("decorator", "@wraps", "functools")),
    ("Генераторы и итераторы", ("generator", "yield", "iterator", "__next__")),
    ("Лямбда-функции и функциональный стиль", ("lambda", "map(", "filter(", "reduce(")),
    ("List comprehension", ("list comprehension", "comprehension")),
    ("Обработка исключений", ("try:", "except", "exception", "raise ", "error handling")),
    ("Циклы", ("for loop", "while loop", "iterate over", "loop through")),
    ("Условия и ветвления", ("if-else", "if else", "conditional statement", "ternary")),
    ("Функции: определение и аргументы", ("def ", "function that", "arguments", "return value", "*args", "**kwargs")),
    ("Оптимизация и рефакторинг кода", ("optimize the", "refactor", "improve the performance", "make the code more efficient", "rewrite the")),
    ("Отладка и исправление кода", ("debug", "fix the error", "find the bug", "correct the code", "what is wrong with")),
)

_LABELS: tuple[str, ...] = tuple(label for label, _ in RULES)


def known_topics() -> tuple[str, ...]:
    """Все лейблы таксономии — для проверки collect.topics и для отчёта."""
    return _LABELS


def classify(*parts: str) -> str | None:
    """Тема строки или None, если ни одно правило не сработало.

    Склеиваем задание, входные данные и код: часть задач опознаётся только
    по коду (импорт pandas), часть — только по формулировке («напиши игру»).
    """
    haystack = "\n".join(p for p in parts if p).lower()
    for label, keywords in RULES:
        for kw in keywords:
            if kw in haystack:
                return label
    return None


def unknown_labels(wanted: Iterable[str]) -> list[str]:
    """Темы из collect.topics, которых нет в таксономии: опечатку ловим сразу."""
    return sorted(set(wanted) - set(_LABELS))


_WS = re.compile(r"\s+")


def clean_instruction(text: str) -> str:
    """Схлопнуть пробелы в формулировке задания: в источнике их неровно."""
    return _WS.sub(" ", text or "").strip()
