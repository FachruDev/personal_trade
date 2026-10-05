FROM python:3.12-slim
WORKDIR /workspace

COPY packages/trading_core/pyproject.toml /workspace/packages/trading_core/pyproject.toml
COPY apps/api/pyproject.toml /workspace/apps/api/pyproject.toml
RUN pip install --no-cache-dir \
    "asyncpg>=0.30,<1" \
    "fastapi>=0.115,<1" \
    "httpx>=0.28,<1" \
    "pydantic-settings>=2.7,<3" \
    "redis>=5.2,<6" \
    "uvicorn[standard]>=0.34,<1"

COPY packages/trading_core /workspace/packages/trading_core
COPY apps/api /workspace/apps/api
RUN pip install --no-cache-dir --no-deps /workspace/packages/trading_core /workspace/apps/api
ENV PYTHONPATH=/workspace/apps/api/src
CMD ["uvicorn", "trading_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
