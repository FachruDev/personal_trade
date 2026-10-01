FROM python:3.12-slim
WORKDIR /workspace
COPY packages/trading_core /workspace/packages/trading_core
COPY apps/api /workspace/apps/api
RUN pip install --no-cache-dir /workspace/packages/trading_core /workspace/apps/api
ENV PYTHONPATH=/workspace/apps/api/src
CMD ["uvicorn", "trading_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
