# Execution ledger — hw11/docs/superpowers/plans/2026-11-15-hw11.md

- Preflight complete: host-before.json; Docker/node limits saved. kind 1.34 Ready, writable containerd tmpfs, no user files deleted and no push.
- Backend primitives: unit RED (NotImplemented), implementation, unit GREEN 6/6. Reused actual HW8–10 verification code, explicit simulated CPU mode.
- Deployment: Helm lint passed; 2 API + 4 client Pods. Prometheus per-Pod/cadvisor and Grafana confirmed up; metrics API recovered after correcting request-timeout < metric-resolution (5s <10s).
- A initial evidence retained including two negative diagnostic results: queue overload with 2 long streams at1.5rps; PID1 self-namespace SIGKILL did not kill. Do not cite those as final PASS.
- A repeat complete: same32s×2rps fresh cold-start schedules; broken36cold503; fixed0cold503 (37 network-unavailable before endpoints); healthy15/15 completed and long streams cross rollout. Source logs and full EndpointSlice/Ready timeline saved.
- Five Kubernetes checks complete PASS: warmup, actual rollback version, rejection/abort accounting, 2-dialogue isolation, Pod replacement with same model SHA + external history. Forcekill from parent PID namespace caused 200 with5parts/noend, aborted; service recovered after actual restart+warmup.
- B complete: 18 independent120s phases; no shortened durations. Backend image1.1 (same cost/queue logic, added Pod/version headers on rejected responses), A used1.0. All compared B phases use1.1.
- C complete: real CPU2→3→2 twice; newPod318uniform/0hot; both alerts pending/firing/recovery. Final audit38PASS.
- Review source identified from supplied lecture11-extended.mp4 at24:40 slide141: Microsoft Philly locality/queue, primary ATC2019 paper linked.

Implementation decisions (within authorized task):
- Use allowed CPU simulator and tiny immutable artifacts, not real weights: all10 points explicitly available under spec. Consequence: TTFC/queue evidence only, no inference-quality or KV-performance claims.
- Containerd uses own8GiBtmpfs because initial disk3.2GiB; volatile monitoring store is intentional, rawresults persist. Consequence: rebuild stand after reboot.
- Fixed routing is sessionAffinity=None, a measured baseline. Consequence: local cache preference is sacrificed; production cache-aware admission requires separate engine measurements.
- Retain full cold-start transport failures rather than suppressing them. Consequence: fixed cold-start run is not misrepresented as continuously available; rollout uses old Ready replicas.
- Keep all work inside the user-requested hw11 directory; do not remove any user files or push. Final local commit will use Dmitry's configured identity.

Final review: no Critical findings. Important reproducibility gap fixed with full run_all workflow and isolated-checkout instructions; reproduction tests RED (missing runner) → GREEN, suite8/8. Minor report chunk-count wording corrected; existing C creation/Ready/318vs0 evidence exposed. No saved request had a completion/chunk mismatch. No user files deleted.
