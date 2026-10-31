"""Six-minute captioned evidence review. Standard AVI/MJPEG writer + Pillow.

No fabricated UI recording: pages identify actual saved artifacts and commands.
Keeps all rendered frames, never deletes source files. No FFmpeg dependency.
"""
import io
import json
from pathlib import Path
import re
import struct
import textwrap
from PIL import Image, ImageDraw, ImageFont

root=Path(__file__).resolve().parents[1]
out=root/'docs/video';out.mkdir(parents=True,exist_ok=True)
font_path='/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
font=ImageFont.truetype(font_path,24)
title_font=ImageFont.truetype(font_path,34)
small=ImageFont.truetype(font_path,20)

def read(name):return (root/name).read_text()
def data(name):return json.loads(read(name))
def log_lines(name,words):
    result=[]
    for line in read('docs/evidence/'+name).splitlines():
        if any(word in line for word in words):result.append(re.sub(r'\x1b\[[0-9;]*m','',line))
    if name=='integration-before.log':
        names=[]
        for line in result:
            if line.startswith('test_'):
                label=line.split(' (')[0]+' -> FAIL'
                if label not in names:names.append(label)
        return '\n'.join(names)+ '\nFAILED (7 incident tests exposed defects)'
    return '\n'.join(result)

summary=data('docs/real/benchmark/summary.json')
gate=data('docs/real/release-report.json')
smoke=data('docs/real/smoke.json')[-1]['body']
manifest=data('docs/real/manifest-baseline.json')
process=data('docs/evidence/process-experiments.json')
http=data('docs/evidence/http-lifecycle.json')
pages=[
('ДЗ 8–10: выпуск модели и API',
'Обзор фактических сохранённых доказательств.\nВидео с титрами, без озвучки; это не live-запись.\n\nИсходный прототип: commit 867cb8f.\nPrefect + FastAPI + Transformers, локально.\nCPU: Ryzen 7 7800X3D; bfloat16, 4 torch threads.\nНового обучения и sweep нет. Push не выполнялся.\n\nПолные команды: README.md\nОтчёт: docs/report.md\nЛоги: docs/evidence/\nРеальные ответы: docs/real/'),
('01. До исправления: семь причин',
'Кеш только по пути; неполная проверка отчёта;\nнеатомарная запись; дубли событий;\nready до прогрева; ID из указателя вместо памяти;\nзапросы без проверки до генерации.\n\n'+log_lines('integration-before.log',['test_http_','test_process_','Ran 7','FAILED'])[:1900]),
('02. Быстрый CI: зелёный и красный',
'$ make check\n13 публичных тестов + 8 интеграционных + 5 safety.\nСобственные проверки повторены с stdlib и FastAPI.\nВеса не загружаются.\n\n'+log_lines('local-ci-green.log',['Ran ','LOCAL CI PASSED'])+'\n\n$ make check-negative\n'+log_lines('local-ci-red.log',['Ran ','FAILED','exit code:'])+'\nПоломка только в отдельной копии; рабочий код сохранён.'),
('03. Prefect: сбой после подготовки',
'Граф: prepare -> obtain artifact -> gate -> publish.\nМежду задачами: URI, ID, хеши. Веса не передаются.\n\n$ python flow.py --workspace WORK --fail-after-prepare\n'+log_lines('process-failure.log',['PREPARED','Flow run','prepare_input','EXIT_CODE='])[:1500]),
('04. Восстановление и инвалидация',
'Новый процесс после сбоя использует persisted cache.\nКлюч: байты входа + tokenizer/template/max_length/code.\n\n'+log_lines('process-recovery.log',['prepare_input','EXIT_CODE='])+'\n\nПосле изменения байтов input.txt по тому же пути:\n'+log_lines('process-invalidation.log',['PREPARED','prepare_input','EXIT_CODE='])+'\n\nИдентичность подготовки не равна ID попытки flow.'),
('05. Отказы сохраняют accepted.json',
'Отчёты running, чужой A и passed=false отвергаются.\n'+ '\n'.join(f"{r['report']}: SHA до == после: {r['unchanged']}" for r in process['rejections'])+'\n\nПример SHA принятого указателя:\n'+process['rejections'][0]['before']+'\n\nNaN/Inf, schema, runtime и ошибка os.replace\nпроверяются неизменёнными публичными тестами.\nПолный контракт: CONTRACTS.txt; код: release.py.'),
('06. Сбой pointer / journal и повтор',
'Сначала durable pending intent, затем atomic pointer,\nзатем целиком atomic journal. Один писатель.\nПовтор восстанавливает pending без двойного события.\n\n'+log_lines('process-pointer-failure.log',['Injected crash','EXIT_CODE='])[:600]+'\n'+log_lines('process-pointer-recovery.log',['publish_accepted','EXIT_CODE='])+'\n\nСобытий публикации после всех повторов: '+str(len(process['publications'].splitlines()))+'\nПопытки отдельно: flow-attempts.jsonl.'),
('07. STUB A -> B -> A с перезапусками',
'Инженерный опыт; это не реальные ответы модели.\n\n'+'\n'.join(f"{r['label']}: HTTP {r['status']}, {r['body'].get('model_id',r['body'].get('ready',''))}" for r in http if r.get('path') in ['/generate','/ready'])+'\n\nПолный транскрипт: docs/evidence/http-lifecycle.json\nНеверный лимит не увеличил backend.calls.'),
('08. Реальные веса и происхождение',
'База: Qwen/Qwen3-0.6B\nCommit: '+manifest['runtime']['base_revision']+'\n\nАдаптер взят из существующего training run:\n3a65e960697647d3baaf701277157296\nMLflow: models:/my-qwen-adapter/2\n\nХеши файлов пересчитаны перед публикацией/загрузкой.\nEval и API: один tokenizer, template, dtype и decode.\nRuntime SHA:\n'+manifest['runtime_sha256']+'\n\nВеса и окружения исключены из Git.'),
('09. Полная оценка и честный отказ',
'По 54 golden + 4 behavioral для обеих моделей.\nПравило quality_gate из ДЗ 6+7 не ослаблено.\n\nBaseline: accuracy 4/54, format 9/54, behavior 0/4.\nCandidate: accuracy 3/54, format 8/54, behavior 0/4.\n\npassed = '+str(gate['passed'])+'\nПричина: '+gate['reason']+'\n\nПрежняя baseline остаётся fallback.\nЕё плохое качество не называется новым PASS.\nРеальный Prefect отказ сохранил SHA accepted.'),
('10. Реальный FastAPI и валидация',
'$ make serve-real\nGET /health -> 200; GET /ready -> 200 после warmup.\nPOST /generate с max_new_tokens=100000 -> 400.\nbackend.calls до/после неправильного запроса равны.\n\nРеальный вопрос: Что выведет print(2 + 3)?\nОтвет: '+smoke['answer']+'\nmodel_id: '+smoke['model_id']+'\noutput_tokens: '+str(smoke['output_tokens'])+'\ngeneration_seconds: '+str(round(smoke['generation_seconds'],3))+'\n\nМетаданные описывают загруженную модель.\nПосле restart вновь загружается принятая baseline.'),
('11. Замер и ограничения',
'Те же 8 запросов, max_new_tokens=32, после warmup.\n\n'+'\n'.join(f"c={r['concurrency']}: {r['successes']}/{r['n']} OK, errors={r['errors']}, {r['success_req_per_second']:.3f} req/s\n  mean={r['mean_success_latency']:.3f}s, max={r['max_success_latency']:.3f}s, tokens={r['output_tokens']}" for r in summary)+'\n\nОдин генератор: c=2 увеличивает очередь, не compute.\nИзмерена полная задержка JSON; TTFT/ITL не измерены.\nНа 8 запросах устойчивый p95 не оценивается.\nPrefill обрабатывает prompt; decode выдаёт токены.\nKV-cache растёт с контекстом и числом последовательностей.\nЭтот опыт не сравнивает SGLang/vLLM.')]

images=[]
for i,(title,body) in enumerate(pages):
    im=Image.new('RGB',(1600,900),'#101827');d=ImageDraw.Draw(im)
    d.rectangle((0,0,1600,100),fill='#18324c')
    d.text((45,28),title,font=title_font,fill='#f4f7ff')
    lines=[]
    for paragraph in body.splitlines():
        lines.extend(textwrap.wrap(paragraph,100,replace_whitespace=False,drop_whitespace=False) or [''])
    if len(lines)>23:raise ValueError(f'Slide {i+1} too long: {len(lines)} lines')
    for n,line in enumerate(lines):d.text((45,125+n*30),line,font=font,fill='#d8e4f0')
    d.text((45,855),f'{i+1:02d}/12 | {i*30//60}:{i*30%60:02d}–{(i+1)*30//60}:{(i+1)*30%60:02d} | фактические логи в docs/evidence/',font=small,fill='#88b5d7')
    im.save(out/f'slide-{i+1:02d}.png')
    buf=io.BytesIO();im.save(buf,format='JPEG',quality=86);images.append(buf.getvalue())

# AVI RIFF chunks, one video stream, 1 frame/s; repeated static pages for 30 seconds.
def chunk(tag,payload):return tag+struct.pack('<I',len(payload))+payload+(b'\0' if len(payload)%2 else b'')
def listing(kind,payload):return chunk(b'LIST',kind+payload)
frames=360
max_size=max(map(len,images))
avih=struct.pack('<14I',1000000,max_size,0,0x10,frames,0,1,max_size,1600,900,0,0,0,0)
strh=struct.pack('<4s4sIHH8I4h',b'vids',b'MJPG',0,0,0,0,1,1,0,frames,max_size,0xffffffff,0,0,0,1600,900)
strf=struct.pack('<IiiHH4sIiiII',40,1600,900,1,24,b'MJPG',1600*900*3,0,0,0,0)
hdrl=listing(b'hdrl',chunk(b'avih',avih)+listing(b'strl',chunk(b'strh',strh)+chunk(b'strf',strf)))
movie=bytearray();index=bytearray();offset=4
for image in images:
    for _ in range(30):
        frame=chunk(b'00dc',image)
        movie.extend(frame);index.extend(struct.pack('<4sIII',b'00dc',0x10,offset,len(image)));offset+=len(frame)
payload=b'AVI '+hdrl+listing(b'movi',movie)+chunk(b'idx1',index)
video=out/'homework8910.avi'
video.write_bytes(b'RIFF'+struct.pack('<I',len(payload))+payload)
print(f'{video}: {frames} frames, 1 fps, 360 seconds, {video.stat().st_size} bytes')
