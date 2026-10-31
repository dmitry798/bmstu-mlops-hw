| Событие | Команды и решение |
|---|---|
| Изменился код | `make check`. Для поведения генерации: `make real-eval`, `make candidate-eval`, `make real-gate`; новый runtime/отчёт. Для документации обучение не нужно. |
| Изменились данные | `python lab.py --workspace WORK run` или `python flow.py --workspace WORK`: содержимое и config меняют ключ подготовки. Для golden/behavioral повторить обе полные оценки и gate. Изменение train требует нового обучения; golden само по себе обучения не требует. |
| Новый адаптер | `python real_release.py candidate-init`, полная оценка baseline/candidate в одном runtime; `make real-gate`, затем flow только при PASS. До PASS accepted остаётся baseline. |

Проверен локальный CI; удалённый Actions не запускался, защита merge не настроена.
