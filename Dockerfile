FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY figma_exporter ./figma_exporter
COPY static ./static
COPY examples ./examples

EXPOSE 8000

CMD ["python", "-m", "figma_exporter"]
