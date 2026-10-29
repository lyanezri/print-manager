FROM python:3.12-slim@sha256:09f7da3bc104798d0afb40bc08d23ab2da20a76130cec1f2ef170848f5d85217

WORKDIR /app

COPY requirements.txt .
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8095

HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
  CMD ["python", "healthcheck.py"]

CMD ["uvicorn", "webapp:app", "--host", "0.0.0.0", "--port", "8095"]
