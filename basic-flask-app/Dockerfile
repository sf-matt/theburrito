FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app app.py .

USER app

EXPOSE 8080

CMD ["gunicorn", "--bind=0.0.0.0:8080", "--access-logfile=-", "--error-logfile=-", "app:app"]
