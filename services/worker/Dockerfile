FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace/services/worker
COPY packages/python-common /workspace/packages/python-common
COPY services/worker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/worker/app ./app
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 CMD ["python", "-m", "app.healthcheck"]
CMD ["python", "-m", "app.main"]
