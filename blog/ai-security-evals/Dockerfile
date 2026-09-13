FROM node:24-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir polyaxon==2.16.4
ENV PATH="/opt/venv/bin:${PATH}"
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY cases.json fixture-provider.cjs promptfooconfig.yaml run.py ./
CMD ["python", "/app/run.py"]
