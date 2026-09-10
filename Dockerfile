FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN pip install --no-cache-dir .
FROM base AS test
RUN pip install --no-cache-dir ".[dev]"
COPY tests ./tests
USER nobody
CMD ["pytest", "-q"]
FROM base AS runtime
USER nobody
EXPOSE 8000
CMD ["uvicorn", "risk_platform.main:app", "--host", "0.0.0.0", "--port", "8000"]
