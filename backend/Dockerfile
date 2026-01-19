FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Docling PDF processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxcb1 \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libfontconfig1 \
    libfreetype6 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python", "server.py"]
