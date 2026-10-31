"""Real HTTP client: every attempt retained, identical inputs at concurrency 1 and 2."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import json
from pathlib import Path
import statistics
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def request(url, payload=None):
    req = Request(url, data=None if payload is None else json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
    with urlopen(req, timeout=180) as response: return response.status, json.load(response)


def benchmark(url, prompts, destination, limit=32):
    destination = Path(destination);destination.mkdir(parents=True, exist_ok=True)
    records, summaries = [], []
    with (destination/'requests.jsonl').open('a') as log:
        for concurrency in [1,2]:
            def one(item):
                index, prompt = item
                start = time.perf_counter()
                record = {'id':f'c{concurrency}-{index}','concurrency':concurrency,'prompt':prompt,'max_new_tokens':limit}
                try:
                    status, response = request(url+'/generate',{'prompt':prompt,'max_new_tokens':limit})
                    record.update(status=status,error=None,**response)
                except HTTPError as exc: record.update(status=exc.code,error=exc.read().decode())
                except Exception as exc: record.update(status=0,error=f'{type(exc).__name__}: {exc}')
                record['client_seconds'] = time.perf_counter()-start
                return record
            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                batch = list(pool.map(one, enumerate(prompts)))
            duration = time.perf_counter()-started
            for record in batch:
                records.append(record);log.write(json.dumps(record,ensure_ascii=False)+'\n');log.flush()
            success = [r for r in batch if r.get('status')==200 and r.get('error') is None]
            errors = [r for r in batch if r not in success]
            summaries.append({'concurrency':concurrency,'n':len(batch),'successes':len(success),'errors':len(errors),'batch_seconds':duration,'success_req_per_second':len(success)/duration,'mean_success_latency':statistics.mean(r['client_seconds'] for r in success) if success else None,'max_success_latency':max((r['client_seconds'] for r in success),default=None),'mean_error_latency':statistics.mean(r['client_seconds'] for r in errors) if errors else None,'max_error_latency':max((r['client_seconds'] for r in errors),default=None),'output_tokens':sum(r.get('output_tokens',0) for r in success)})
    (destination/'summary.json').write_text(json.dumps(summaries,indent=2)+'\n')
    with (destination/'summary.csv').open('w') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(summaries[0]),lineterminator="\n");writer.writeheader();writer.writerows(summaries)
    return summaries

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8091');p.add_argument('--golden',type=Path,default=Path('../hw67-broken/data/eval/golden.jsonl'));p.add_argument('--output',type=Path,default=Path('docs/real/benchmark'));p.add_argument('--n',type=int,default=8)
    a=p.parse_args();prompts=[json.loads(line)['input'] for line in a.golden.read_text().splitlines()][:a.n]
    print(json.dumps(benchmark(a.url,prompts,a.output),indent=2))
