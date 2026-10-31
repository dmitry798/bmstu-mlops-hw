"""FastAPI adapter with injectable backend and background initialization."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from service_core import ServiceState, StubBackend, Unavailable


def create_app(root, warmup_seconds=0, backend_factory=StubBackend):
    @asynccontextmanager
    async def lifespan(app):
        app.state.model = ServiceState(root, warmup_seconds, backend_factory)
        yield
    app = FastAPI(lifespan=lifespan)
    @app.get('/health')
    def health(): return {'alive':True, 'backend':backend_factory.label}
    @app.get('/ready')
    def ready():
        state = app.state.model
        return JSONResponse({'ready':state.ready}, status_code=200 if state.ready else 503)
    @app.get('/debug', include_in_schema=False)
    def debug(): return app.state.model.debug()
    @app.post('/generate')
    async def generate(request: Request):
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 65536: return JSONResponse({'error':'body too large'}, status_code=413)
        import json
        try:
            payload = json.loads(body)
            return await run_in_threadpool(app.state.model.generate, payload)
        except Unavailable as exc:
            return JSONResponse({'error':str(exc)}, status_code=503)
        except (ValueError, TypeError) as exc:
            return JSONResponse({'error':str(exc)}, status_code=400)
    return app
