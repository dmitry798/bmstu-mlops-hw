#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
export KUBECONFIG="$PWD/hw11/.local/kubeconfig"
export PATH="$PWD/hw11/.tools:$PATH"
mkdir -p hw11/.local hw11/results/preflight
# Preserve existing resources; these names belong only to this homework.
df -h .
docker info --format 'Docker={{.ServerVersion}} Cgroup={{.CgroupVersion}} CPUs={{.NCPU}} RAM={{.MemTotal}} Root={{.DockerRootDir}} Driver={{.Driver}}' > hw11/results/preflight/docker-info.txt
# The dedicated tmpfs holds preloaded kind CRI images plus all experiment images.
docker volume inspect hw11-containerd >/dev/null 2>&1 || docker volume create --driver local --opt type=tmpfs --opt device=tmpfs --opt o=size=8g,mode=0755 hw11-containerd
# Rebind the volume after reboot: an already-running node can retain the disk directory.
if docker inspect hw11-control-plane >/dev/null 2>&1; then docker stop hw11-control-plane >/dev/null; fi
node_image='kindest/node:v1.34.0@sha256:7416a61b42b1662ca6ca89f02028ac133a309a2a30ba309614e8ec94d976dc5a'
if ! docker inspect hw11-storage-holder >/dev/null 2>&1; then
  docker run -d --name hw11-storage-holder --read-only --memory 6g --memory-swap 6g --cpus 1 --pids-limit 32 -v hw11-containerd:/storage --entrypoint /bin/sh "$node_image" -c 'sleep infinity'
fi
docker start hw11-storage-holder >/dev/null
if ! docker exec hw11-storage-holder test -d /storage/io.containerd.metadata.v1.bolt; then
  if ! docker inspect hw11-node-seed >/dev/null 2>&1; then
    docker run -d --name hw11-node-seed --read-only --memory 128m --entrypoint /bin/sh "$node_image" -c 'sleep infinity'
  fi
  docker start hw11-node-seed >/dev/null
  docker cp hw11-node-seed:/var/lib/containerd/. - | docker exec -i hw11-storage-holder tar -xf - -C /storage
fi
if docker inspect hw11-control-plane >/dev/null 2>&1; then docker start hw11-control-plane >/dev/null; fi
kind get clusters | rg -x hw11 || kind create cluster --name hw11 --config hw11/kind.yaml --kubeconfig "$KUBECONFIG" --wait 120s
docker update --memory 8g --memory-swap 8g --cpus 6 hw11-control-plane
docker build -f hw11/Dockerfile -t hw11-api:1.1 .
kind load docker-image hw11-api:1.1 --name hw11
helm upgrade --install hw11 hw11/charts/hw11 -n hw11 --create-namespace --set image=hw11-api:1.1
kubectl -n hw11 apply -f hw11/monitoring/stack.yaml
kubectl apply -f hw11/monitoring/metrics-server.yaml
kubectl -n hw11 rollout status deployment/hw11-api --timeout=180s
