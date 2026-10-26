FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace/services/orders
COPY packages/python-common /workspace/packages/python-common
COPY services/orders/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/orders/app ./app
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/workspace"]
