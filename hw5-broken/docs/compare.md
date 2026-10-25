# Базовая модель против адаптера

Адаптер: `models/adapter_all_layers`. Генерация жадная, до 80 токенов.

## 1. Write a Python function to reverse a string.

**База:**

> ```python / def reverse_string(input_string): /     return input_string[::-1] / ```

**Адаптер:**

> def reverse_string(string): /     reversed_string = string[::-1] /     return reversed_string

## 2. Write a Python function that checks whether a number is prime.

**База:**

> ```python / def is_prime(num): /     if num < 2: /         return False /     for i in range(2, int(num**0.5) + 1): /         if num % i == 0: /             return False /     return True / ```

**Адаптер:**

> def is_prime(num): /     if num < 2: /         return False /     for i in range(2, num): /         if num % i == 0: /             return False /     return True

## 3. Create a Python program that counts the frequency of each word in a sentence.

**База:**

> ```python / sentence = 'the quick brown fox jumps over the lazy dog the end' / word_counts = {} / for word in sentence.split(): /     word_counts[word] = word_counts.get(word, 0) + 1 / print(word_counts) / ```

**Адаптер:**

> from collections import Counter /  / def count_words(sentence): /     words = sentence.split() /     return Counter(words) /  / print(count_words(sentence))

## 4. Write a Python function to compute the factorial of a number using recursion.

**База:**

> ```python / def factorial(n): /     if n == 0 or n == 1: /         return 1 /     else: /         return n * factorial(n - 1) / ```

**Адаптер:**

> def factorial(n): /     if n == 0: /         return 1 /     else: /         return n * factorial(n-1)

## 5. Write a Python script that reads a CSV file and prints the number of rows.

**База:**

> ```python / import csv /  / with open("data.csv", "r") as file: /     reader = csv.reader(file) /     print(len(reader)) / ```

**Адаптер:**

> import csv /  / with open('data.csv', 'r') as csvfile: /     reader = csv.reader(csvfile) /     count = 0 /     for row in reader: /         count += 1 /     print(count)
