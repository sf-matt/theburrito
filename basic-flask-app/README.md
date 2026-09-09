# Basic Flask App

A minimal Flask app with one `GET /` route, packaged as a container for quick
CloudSecBurrito demos and labs.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
curl http://localhost:8080/
```

Override the response text with `APP_MESSAGE`:

```bash
APP_MESSAGE="Hello from the lab" python app.py
```

## Run the container

```bash
docker build -t basic-flask-app .
docker run --rm -p 8080:8080 basic-flask-app
```

After a publish workflow completes, pull it from GHCR:

```bash
docker pull ghcr.io/sf-matt/basic-flask-app:latest
```

The workflow publishes `latest` from the default branch, a short commit SHA
tag, and version tags when run against a tag such as `v1.0.0`.
