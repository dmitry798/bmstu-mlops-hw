.PHONY: install fetch repro v1 v2 diff dag diversity contamination stats check clean

install:
	uv sync

fetch:
	uv run python scripts/fetch_dataset.py

repro:
	uv run dvc repro

v1:
	uv run python scripts/set_version.py v1
	uv run dvc repro

v2:
	uv run python scripts/set_version.py v2
	uv run dvc repro

diff:
	uv run dvc metrics diff

dag:
	uv run dvc dag

diversity:
	uv run python -m src.diversity

contamination:
	uv run python scripts/check_contamination.py

stats:
	uv run python scripts/datasheet_stats.py

check:
	bash tests/check.sh

clean:
	rm -rf data/raw.jsonl data/clean.jsonl data/train.jsonl data/val.jsonl \
		data/test.jsonl data/_check metrics/*.json params.yaml.bak params.yaml.orig
