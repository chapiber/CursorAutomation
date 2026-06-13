FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    rsync \
    openssh-client \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Deploy scripts montés via volume dans docker-compose
ENV PYTHONUNBUFFERED=1
ENV CONFIG_DIR=/config
ENV WORKSPACE_DIR=/workspaces

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
