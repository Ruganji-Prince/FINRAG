FROM python:3.14-slim
WORKDIR /app
ARG INSTALL_SEMANTIC=true
COPY requirements*.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip==26.3
RUN if [ "$INSTALL_SEMANTIC" = "true" ]; then pip install --no-cache-dir -r requirements-embeddings.txt; else pip install --no-cache-dir -r requirements.txt; fi
COPY . .
RUN useradd -m finrag && mkdir -p /app/data /app/.models && chown -R finrag /app
USER finrag
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
