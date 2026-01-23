FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN pip install mcpo uvicorn

ENTRYPOINT ["mcpo"]
CMD ["--server-type", "streamable_http", "--port", "8080", "--host", "0.0.0.0", "--", "http://localhost:8000/mcp"]
