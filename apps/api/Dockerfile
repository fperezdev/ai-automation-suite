FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY apps/api/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY apps/api /app
COPY db /db

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${API_PORT:-8000}"]
