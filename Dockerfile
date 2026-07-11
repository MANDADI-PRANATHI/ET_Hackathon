# The app container — everything needed to serve the API + UI.
# Real documents and the ingested graph are bind-mounted from data/ (see
# docker-compose.yml), not baked into the image, so they stay organized on
# your host disk and survive rebuilding the image.
#
# Off by default: INSTALL_PDF=false. PDF/Word reading (Docling) pulls in
# torch/transformers for layout analysis + OCR -- several GB -- so it's only
# installed when explicitly requested (see docker-compose.yml / README).
FROM python:3.11-slim

WORKDIR /app
ARG INSTALL_PDF=false

# Install dependencies first so this layer is cached across code changes.
COPY requirements-docker.txt requirements-l0.txt requirements-pdf.txt ./
RUN pip install --no-cache-dir -r requirements-docker.txt \
 && if [ "$INSTALL_PDF" = "true" ]; then pip install --no-cache-dir -r requirements-pdf.txt; fi

COPY src/ src/
COPY scripts/ scripts/
COPY config/ config/
COPY web/ web/
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

ENV PYTHONPATH=/app/src
EXPOSE 8000

CMD ["./docker-entrypoint.sh"]
