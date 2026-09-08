# AstroChecker for Cloud Run or any HTTPS proxy. Base pinned by digest so the
# release workflow rebuilds the same image; bump the digest on purpose.
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    XDG_CONFIG_HOME=/tmp/.config \
    XDG_CACHE_HOME=/tmp/.cache

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY astrochecker ./astrochecker
COPY data/catalog.sqlite3 ./data/catalog.sqlite3
COPY run.py ./

RUN useradd --system --uid 10001 --no-create-home astrochecker
USER astrochecker

EXPOSE 8080
# ASTROCHECKER_PUBLIC_HOST must be set by the platform to the published hostname:
# it turns on the stateless cloud mode (no site file, NINA files as downloads).
CMD ["python", "run.py", "--no-browser", "--host", "0.0.0.0"]
