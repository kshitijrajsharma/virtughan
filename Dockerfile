## docker build -t virtughan . && docker run --rm --name virtughan -p 8080:8080 virtughan

# Build stage
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgdal-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install poetry

WORKDIR /app

COPY . .

RUN poetry config virtualenvs.create false && poetry install --no-interaction 


# Final stage
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /app /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

EXPOSE 8080

CMD ["uvicorn", "API:app", "--host", "0.0.0.0", "--port", "8080"]