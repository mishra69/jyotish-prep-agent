# Chart API image. Build from the repo root so astro/ is in the context:
#   gcloud builds submit --config=api/cloudbuild.yaml .
FROM python:3.11-slim
WORKDIR /app

COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt

COPY astro/ astro/
COPY api/ api/

ENV PORT=8080
EXPOSE 8080
CMD exec uvicorn api.main:app --host 0.0.0.0 --port $PORT
