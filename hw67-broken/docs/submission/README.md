# Артефакты сдачи (копия metrics/, который исключён .gitignore)

- MLflow UI: http://127.0.0.1:5006
- Sweep: эксперимент `hw6-lora`, parent run `651e41f3b4ff4aada3ff599176cf1b4f`
- Candidate: `models:/my-qwen-adapter/2` (alias `candidate`), run `3a65e960697647d3baaf701277157296`
- Оценка: эксперимент `hw67-evaluation`, run `7ec864962e2140c1b387d1d3a55e7a59`
  (там же все *-outputs.json, *-eval.json, eval-diff.json, params.json, baseline.json)
- Storage probe run: см. `storage-check.json`
- Данные оценки: DVC, `dvc pull` (remote `../hw67-dvc-storage`); пересборка `dvc repro`
