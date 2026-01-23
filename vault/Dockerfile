FROM python:3.11-slim

# Create non-root user
RUN useradd -m -s /bin/bash appuser

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY main.py .

# Switch to non-root user
USER appuser

# Default command (library - no standalone execution needed)
CMD ["python", "-c", "print('SAGE Vault module ready for import')"]
