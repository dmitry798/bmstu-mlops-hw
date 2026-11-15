# ДЗ11: Kubernetes под нагрузкой

Управляемый CPU backend (`backend_mode=simulated`), продолжение контракта артефактов и `ServiceState` из ДЗ8–10. Реальные kind/Kubernetes, HTTP, четыре клиентских Pod, Prometheus, Grafana, metrics-server и HPA. Веса LLM не скачиваются. Предыдущие ДЗ не изменяются.

## Запуск

Из корня репозитория. Нужны Docker, curl, tar, uv; Docker должен быть доступен пользователю. Закреплённые инструменты: kind v0.30.0, kubectl v1.34.0, Helm v3.19.0. Установите их из официальных release assets в `hw11/.tools/` (либо используйте эти версии в PATH).

```bash
mkdir -p hw11/.tools
curl -fL https://kind.sigs.k8s.io/dl/v0.30.0/kind-linux-amd64 -o hw11/.tools/kind
curl -fL https://dl.k8s.io/release/v1.34.0/bin/linux/amd64/kubectl -o hw11/.tools/kubectl
curl -fL https://get.helm.sh/helm-v3.19.0-linux-amd64.tar.gz -o /tmp/hw11-helm.tar.gz
tar -xzf /tmp/hw11-helm.tar.gz -C /tmp
cp /tmp/linux-amd64/helm hw11/.tools/helm
chmod +x hw11/.tools/{kind,kubectl,helm}
uv venv hw11/.venv
uv pip install --python hw11/.venv/bin/python -r hw11/requirements-analysis.lock
bash hw11/scripts/setup.sh
export KUBECONFIG="$PWD/hw11/.local/kubeconfig"
export PATH="$PWD/hw11/.tools:$PATH"
kubectl -n hw11 get pods -o wide
kubectl top pods -n hw11
```

Адреса на локальном компьютере: API http://127.0.0.1:18080 ; Prometheus http://127.0.0.1:19090 ; Grafana http://127.0.0.1:13000/d/hw11 . Нагрузочные запросы идут **из Pod через ClusterIP**, port-forward используется только для управления клиентами.

## Опыты

Полный повтор запускается в **отдельном checkout**, чтобы не перезаписать сохранённые доказательства. Скрипты используют `hw11/results` относительно своего checkout; произвольный путь результатов они не поддерживают. Сначала вручную выполните команды удаления **только собственного стенда** из раздела ниже (kind, holder/seed, tmpfs volume). Другие ресурсы не трогать. Затем:

```bash
# Из исходного репозитория; оригинальные результаты остаются на месте:
git worktree add ../bmstu-hw11-rerun HEAD
cd ../bmstu-hw11-rerun
# Сохранить копию опубликованных результатов, ничего не удаляя:
mv hw11/results hw11/results-submitted
mkdir hw11/results
# Установить закреплённые tools/.venv по разделу «Запуск» выше.
hw11/.venv/bin/python hw11/scripts/run_all.py --plan
hw11/.venv/bin/python hw11/scripts/run_all.py
```

`run_all.py` отказывается работать с непустой results и существующим собственным кластером/holder. Он фиксирует preflight, запускает setup, сохраняет журналы Pod, выполняет A/RED/GREEN/пять проверок, записывает актуальный baseline двух Pod перед B, выполняет все18фаз и C. Затем выгружает ряды Prometheus, считает network/hot/warmup/HPA-анализ, строит четыре графика, проверяет реальный Grafana, запускает аудит, сохраняет размеры и генерирует report.html. Любой сбой останавливает последовательность. Полный повтор занимает около50минут. Старые JSON из results-submitted не используются аудитом. `run_all.py --plan` безопасно показывает полный порядок без запуска.

Отдельные скрипты можно запускать для диагностики, но это не заменяет полный сценарий. Повторное имя job отвергается, историю cohort phase нужно начинать со свежего Prometheus. Короткая проверка:

```bash
PYTHONPATH=hw11 hw11/.venv/bin/python -m unittest discover -s hw11/tests -v
```

`experiment_a.py` — сохранённая первоначальная диагностика. Проверки окончательного результата: `checks-a-repeat.json`, `kubernetes-checks.json`, `audit.json`. Исходные отрицательные проверки не скрыты: перегрузка очереди при двух длинных потоках и попытка SIGKILL PID1 из того же PID namespace. Исправленный kill направляется в проверенный PID нужного контейнера из родительского namespace узла kind.

## Ресурсы и удаление своего стенда

Один узел ограничен 6 CPU / 8 GiB RAM, containerd на отдельном tmpfs 8 GiB. Источник артефакта — immutable ConfigMap A/B, file inventory SHA256 и runtime SHA256 проверяет код из предыдущего ДЗ. Prometheus retention 2 h / 256 MB, том 384 MiB; Grafana том 128 MiB. Все данные стенда в tmpfs исчезнут после перезагрузки, исходники/сырые результаты сохраняются на диске. Нет требования сохранять метрики между перезагрузками.

Команды ниже **не запускались автоматически**. Они удаляют только ресурсы этого ДЗ. Общие prune/удаление других томов запрещены.

```bash
export KUBECONFIG="$PWD/hw11/.local/kubeconfig"
hw11/.tools/kind delete cluster --name hw11
# Освободить выделенный RAM-том после остановки именно собственного держателя:
docker stop hw11-storage-holder hw11-node-seed
docker rm hw11-storage-holder hw11-node-seed
docker volume rm hw11-containerd
# Необязательно: удалить только два образа приложения этого ДЗ:
docker image rm hw11-api:1.0 hw11-api:1.1
```

Kind node image может использоваться другими кластерами: его не удалять без проверки. Собственные cluster-scoped monitoring RBAC и metrics-server исчезают вместе с узлом kind. Фактические размеры, imageIDs и лимиты — в `results/preflight/` и отчёте. Git push не выполняется.
