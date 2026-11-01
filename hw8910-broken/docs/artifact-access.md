# Получение и проверка артефактов

Код, отчёты, исходные ответы и хеши — в репозитории hw8910-broken.
Видео MP4 и evaluation-artifacts-final.tar.gz прикладываются отдельно.
Архив содержит golden/behavioral/training-index и все отчёты, включая
сырые ответы и benchmark-final из итоговой записи. Веса в архив не входят.

Проверка архива после распаковки: sha256sum -c SHA256SUMS.
Данные расположены по исходным путям hw67-broken/data/eval/.
Их хеши сверяются с manifest и полными eval, а не с ручным passed=true.

Проверка полного gate по сохранённым ответам не требует весов и MLflow:
.venv/bin/python real_release.py current-gate --workspace docs/real
Ожидается exit 1: регрессия accuracy, а не ошибка доступа к модели.

Принятая baseline общедоступна на Hugging Face, точная ревизия:
https://huggingface.co/Qwen/Qwen3-0.6B/tree/c1899de289a04d12100db370d81485cdf75e47ca

Получение тех же весов из Python:
from huggingface_hub import snapshot_download
snapshot_download('Qwen/Qwen3-0.6B',
    revision='c1899de289a04d12100db370d81485cdf75e47ca')

Отклонённый адаптер: training run 3a65e960697647d3baaf701277157296,
models:/my-qwen-adapter/2. Источник — прежний локальный MLflow :5006.
Веса адаптера не публиковались и не включены в Git/архив сдачи.
Для повторной генерации кандидата нужен read-доступ к этому MLflow
(на данном ПК либо через согласованный SSH-туннель); после получения
доступа команда: python scripts/fetch_candidate.py --tracking-uri URL.
Публичной ссылки на адаптер нет; localhost не выдаётся за внешний URL.
Для проверки API baseline адаптер не требуется: используются публичные веса.
