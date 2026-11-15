FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c
WORKDIR /app
COPY hw11/requirements-runtime.lock /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY hw8910-broken/service_core.py hw8910-broken/release.py /app/vendor/hw8910/
COPY hw11/app /app/app
ENV HW8910_SOURCE=/app/vendor/hw8910 PYTHONUNBUFFERED=1
USER 10001
CMD ["python","-m","uvicorn","app.server:app","--host","0.0.0.0","--port","8000","--timeout-graceful-shutdown","35"]
