FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./

ENV POLL_INTERVAL=2
ENV HEARTBEAT_INTERVAL=15
ENV MODE=kata

CMD ["python", "sensor.py"]