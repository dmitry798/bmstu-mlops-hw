PYTHON ?= .venv/bin/python
MODEL_PYTHON ?= ../hw67-broken/.venv/bin/python
.PHONY: check check-core check-negative init flow serve serve-real real-init real-eval benchmark
check:
	$(PYTHON) scripts/check.py
check-core:
	$(PYTHON) -m unittest discover -s tests -v
check-negative:
	$(PYTHON) scripts/negative_ci.py
init:
	$(PYTHON) lab.py init
flow:
	$(PYTHON) flow.py --workspace .lab
serve:
	$(PYTHON) service.py --framework fastapi --workspace .lab --warmup-seconds 2
real-init:
	$(MODEL_PYTHON) real_release.py init
real-eval:
	$(MODEL_PYTHON) real_release.py evaluate
serve-real:
	$(MODEL_PYTHON) service.py --framework fastapi --backend transformers --workspace .real --warmup-seconds 0
benchmark:
	$(PYTHON) scripts/benchmark.py
.PHONY: candidate-init candidate-eval real-gate real-flow prove-process
candidate-init:
	$(MODEL_PYTHON) real_release.py candidate-init
candidate-eval:
	$(MODEL_PYTHON) real_release.py candidate-evaluate
real-gate:
	$(PYTHON) real_release.py current-gate
real-flow:
	$(PYTHON) flow.py --workspace .real --manifest manifest-candidate.json --report release-report.json
prove-process:
	$(PYTHON) scripts/prove_process.py
