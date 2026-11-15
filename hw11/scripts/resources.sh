#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
{
 date -Is
 df -h .
 free -h
 docker stats --no-stream --format '{{.Name}} {{.MemUsage}} CPU={{.CPUPerc}}'
 docker image ls --digests --format '{{.Repository}}:{{.Tag}} {{.Digest}} {{.Size}}'
 docker exec hw11-control-plane du -sh /var/lib/containerd
 du -sh hw11/results hw11/.tools hw11/.venv hw11/videos
 hw11/.tools/kubectl --kubeconfig hw11/.local/kubeconfig -n hw11 top pods
} > hw11/results/preflight/resources-after.txt
cat hw11/results/preflight/resources-after.txt
