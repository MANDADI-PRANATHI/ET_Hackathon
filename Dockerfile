# The app container — everything needed to serve the API + UI.
# Real documents and the ingested graph are bind-mounted from data/ (see
# docker-compose.yml), not baked into the image, so they stay organized on
# your host disk and survive rebuilding the image.
#
# Deliberately lightweight: no docling, no torch (see requirements-docker.txt
# for why). Reading real PDF files is a separate, one-time local step
# (`python run.py --full`), not baked into the always-on server image.
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first so this layer is cached across code changes.
COPY requirements-docker.txt requirements-l0.txt ./
RUN pip install --no-cache-dir -r requirements-docker.txt

COPY src/ src/
COPY scripts/ scripts/
COPY config/ config/
COPY web/ web/
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

ENV PYTHONPATH=/app/src
EXPOSE 8000

CMD ["./docker-entrypoint.sh"]
