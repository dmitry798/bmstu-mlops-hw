"""Лёгкий HTTP-прототип с дефектами. Только localhost, STUB ONLY.

Для итогового проекта перенесите исправленный контракт в FastAPI и подключите
загрузчик ДЗ 6+7. Прототип нужен для опытов без установки зависимостей и весов.
"""
import argparse
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


from service_core import StubBackend, ServiceState, Unavailable


def handler_for(state):
    class Handler(BaseHTTPRequestHandler):
        def send_json(self,status,payload):
            data=json.dumps(payload,ensure_ascii=False).encode()
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)

        def do_GET(self):
            if self.path=='/health':self.send_json(200,{'alive':True,'backend':'STUB ONLY'})
            elif self.path=='/ready':self.send_json(200 if state.ready else 503,{'ready':state.ready})
            elif self.path=='/debug':
                self.send_json(200,state.debug())
            else:self.send_json(404,{'error':'not found'})

        def do_POST(self):
            if self.path!='/generate':self.send_json(404,{'error':'not found'});return
            try:size=int(self.headers.get('Content-Length','0'))
            except ValueError:
                self.send_json(400,{'error':'invalid Content-Length'});return
            if size<0 or size>65536:self.send_json(413,{'error':'body too large'});return
            try:
                payload=json.loads(self.rfile.read(size))
                self.send_json(200,state.generate(payload))
            except Unavailable as e:
                self.send_json(503,{'error':str(e)})
            except (ValueError,TypeError,AttributeError,KeyError) as e:
                self.send_json(400,{'error':str(e)})
    return Handler


def main():
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,default=Path('.lab'))
    p.add_argument('--port',type=int,default=8091);p.add_argument('--warmup-seconds',type=float,default=5)
    p.add_argument('--framework',choices=['stdlib','fastapi'],default='stdlib')
    p.add_argument('--backend',choices=['stub','transformers'],default='stub')
    args=p.parse_args()
    from service_core import TransformersBackend
    factory=StubBackend if args.backend=='stub' else TransformersBackend
    if args.framework=='fastapi':
        import uvicorn
        from api import create_app
        uvicorn.run(create_app(args.workspace,args.warmup_seconds,factory),host='127.0.0.1',port=args.port)
        return
    state=ServiceState(args.workspace,args.warmup_seconds,factory)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler_for(state))
    print(f'STUB ONLY: http://127.0.0.1:{server.server_port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
