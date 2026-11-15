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

Нельзя одновременно запускать несколько orchestrator: они меняют общий стенд. Сохранённые результаты находятся в `results/`. Для полного повторного измерения создайте свежий собственный кластер/Prometheus и отдельную директорию результатов: client jobs и cohort phase не должны смешиваться с прошлой серией. begin() отвергает повторное имя job; данные предыдущего прогона не выдаются за новые.

```bash
PYTHONPATH=hw11 hw11/.venv/bin/python -m unittest discover -s hw11/tests -v
# A исходный диагностический прогон (сохраняет также отрицательные наблюдения):
hw11/.venv/bin/python hw11/scripts/experiment_a.py
# Одинаковые cold-start опыты RED/GREEN + штатный rollout при .2 req/s:
hw11/.venv/bin/python hw11/scripts/recheck_a.py
# Пять Kubernetes-проверок, включая аварийный kill из родительского PID namespace:
hw11/.venv/bin/python hw11/scripts/kubernetes_checks.py
# Убедиться, что HPA ещё не включён; две Ready-реплики, backend одинаковый:
hw11/.venv/bin/python hw11/scripts/experiments.py B
# 18 фаз по 120 с + дренирование очереди; длительность около 40 минут.
hw11/.venv/bin/python hw11/scripts/experiment_c.py
hw11/.venv/bin/python hw11/scripts/analyze.py
hw11/.venv/bin/python hw11/scripts/audit.py
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
