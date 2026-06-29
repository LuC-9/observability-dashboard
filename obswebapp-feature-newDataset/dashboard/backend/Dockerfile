FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
ENV CENTRAL_PROJECT=oa-apmena-observability-dv GOLD_DATASET=gold
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
