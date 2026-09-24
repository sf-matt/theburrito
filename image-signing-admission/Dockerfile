FROM python:3.13-slim@sha256:8d9d0b8bcf6506481eae4907c18f5e3e7902e629f5f6d684f9e7c32e85e3ddf0

ARG DEMO_VARIANT=unsigned

LABEL org.opencontainers.image.source="https://github.com/sf-matt/theburrito" \
      io.cloudsecburrito.cosign-demo="${DEMO_VARIANT}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app app.py .

USER app

EXPOSE 8080

CMD ["gunicorn", "--bind=0.0.0.0:8080", "--access-logfile=-", "--error-logfile=-", "app:app"]
