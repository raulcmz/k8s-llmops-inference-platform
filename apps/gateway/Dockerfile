FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV OLLAMA_BASE_URL=http://ollama:11434
ENV DEFAULT_MODEL=mistral:7b

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]