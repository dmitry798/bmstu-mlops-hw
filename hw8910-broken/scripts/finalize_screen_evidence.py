"""Validate the recorded benchmark, synchronize its report, package weight-free evidence."""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import statistics
import tarfile

ROOT=Path(__file__).resolve().parents[1]
PREVIOUS=ROOT.parent/'hw67-broken'


def finalize(source, package=True):
    source=Path(source).resolve()
    summaries=json.loads((source/'summary.json').read_text())
    records=[json.loads(line) for line in (source/'requests.jsonl').read_text().splitlines() if line.strip()]
    accepted=json.loads((ROOT/'.real/accepted.json').read_text())
    assert len(records)==16 and {s['concurrency'] for s in summaries}=={1,2}
    prompts=[]
    for summary in summaries:
        batch=[r for r in records if r['concurrency']==summary['concurrency']]
        assert len(batch)==8 and len({r['id'] for r in batch})==8
        prompts.append([r['prompt'] for r in batch])
        assert all(r['max_new_tokens']==32 for r in batch)
        successful=[r for r in batch if r['status']==200 and r['error'] is None]
        assert all(r['model_id']==accepted['model_id'] and r['runtime_sha256']==accepted['runtime_sha256'] for r in successful)
        assert summary['successes']==len(successful) and summary['errors']==len(batch)-len(successful)
        assert summary['output_tokens']==sum(r['output_tokens'] for r in successful)
        assert math.isclose(summary['success_req_per_second'],len(successful)/summary['batch_seconds'])
        assert math.isclose(summary['mean_success_latency'],statistics.mean(r['client_seconds'] for r in successful))
        assert math.isclose(summary['max_success_latency'],max(r['client_seconds'] for r in successful))
    assert prompts[0]==prompts[1]
    destination=ROOT/'docs/real/benchmark-final'
    destination.mkdir(parents=True,exist_ok=True)
    for name in ['requests.jsonl','summary.json','summary.csv']:
        shutil.copy2(source/name,destination/name)
    def number(x):return f'{x:.3f}'.replace('.',',')
    table='| Concurrency | n | Успехи / ошибки | Пакет, с | req/s | Mean / max, с | Токены |\n|---|---:|---:|---:|---:|---:|---:|\n'
    for s in sorted(summaries,key=lambda s:s['concurrency']):
        table+=f"| {s['concurrency']} | {s['n']} | {s['successes']} / {s['errors']} | {number(s['batch_seconds'])} | {number(s['success_req_per_second'])} | {number(s['mean_success_latency'])} / {number(s['max_success_latency'])} | {s['output_tokens']} |\n"
    report_path=ROOT/'docs/report.md'
    report=report_path.read_text()
    start=report.index('| Concurrency |')
    end=report.index('\n\n',start)
    report=report[:start]+table.rstrip()+report[end:]
    report=report.replace('(real/benchmark/requests.jsonl)','(real/benchmark-final/requests.jsonl)')
    old='Одно шестиминутное видео с титрами собирает фактические сохранённые логи: `docs/video/homework8910.avi`. Это обзор доказательств, не live-запись; [сценарий](video-script.md) позволяет записать собственный показ. AVI и кадры не входят в Git, приложить отдельно. Никакой внешней публикации не выполнялось.'
    new='Итоговое видео — настоящий захват экрана OBS, 1920×1080, MP4, без озвучки и титров, длительность 5–8 минут. В нём команды реально выполняются в терминале; таблица выше и `docs/real/benchmark-final/` относятся именно к этому показу. Предыдущий замер сохранён отдельно в `docs/real/benchmark/`. Видео находится в `docs/video/` и прикладывается отдельно от Git. Сценарий: [video-script.md](video-script.md). Никакой внешней публикации не выполнялось.'
    report=report.replace(old,new)
    report_path.write_text(report)
    text='# Замер из итоговой записи экрана\n\n'+table+'\n'
    for s in sorted(summaries,key=lambda s:s['concurrency']):
        good=[r for r in records if r['concurrency']==s['concurrency'] and r['status']==200 and r['error'] is None]
        text+=f"c={s['concurrency']}: среднее вычисление {number(statistics.mean(r['generation_seconds'] for r in good))} с; ожидание {number(statistics.mean(r['queue_seconds'] for r in good))} с.\n"
    text+='''
Генератор один: второй HTTP-запрос ждёт lock, поэтому рост concurrency
увеличивает очередь и latency, но почти не меняет throughput.
Ошибки не удаляются: их latency считается отдельно; при отсутствии — null.
Все 16 попыток: docs/real/benchmark-final/requests.jsonl.

Prefill обрабатывает prompt и строит attention-состояние.
Decode последовательно выдаёт токены, используя ранее сохранённые K и V.
KV-cache растёт с контекстом, числом последовательностей, слоями/KV-heads
и размером dtype: примерно 2 × layers × kv_heads × head_dim × tokens × bytes.

Измерена полная задержка одного JSON-ответа. TTFT и ITL не измерялись.
На восьми запросах нельзя делать вывод об устойчивом p95.
Последовательный Transformers с lock не проверяет скорость SGLang/vLLM:
здесь не измерялись их continuous batching и управление KV-cache.
'''
    (ROOT/'docs/measurements-final.md').write_text(text)
    if package:
        entries={}
        for path in sorted((ROOT/'docs').rglob('*')):
            if path.is_file() and path.parts[len(ROOT.parts)+1] != 'video':
                entries[str(Path('hw8910-broken')/path.relative_to(ROOT))]=path
        for name in ['golden.jsonl','behavioral.jsonl','training-index.jsonl','training-index-proof.json']:
            entries['hw67-broken/data/eval/'+name]=PREVIOUS/'data/eval'/name
        for name in ['params.json','baseline.json','solution.py','contract.py']:
            entries['hw67-broken/evaluation/'+name]=PREVIOUS/'evaluation'/name
        assert not any(Path(name).suffix in ['.safetensors','.pt','.bin','.env'] for name in entries)
        hashes=''.join(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+name+'\n' for name,path in sorted(entries.items()))
        output=ROOT/'docs/video/evaluation-artifacts-final.tar.gz'
        output.parent.mkdir(parents=True,exist_ok=True)
        with tarfile.open(output,'w:gz') as archive:
            for name,path in sorted(entries.items()):archive.add(path,arcname=name,recursive=False)
            payload=hashes.encode();info=tarfile.TarInfo('SHA256SUMS');info.size=len(payload);archive.addfile(info,io.BytesIO(payload))
        print(output.relative_to(ROOT))
        print(hashlib.sha256(output.read_bytes()).hexdigest())
    print(table)
    return summaries

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('benchmark',type=Path);parser.add_argument('--no-package',action='store_true');args=parser.parse_args()
    finalize(args.benchmark,not args.no_package)
