FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY alembic.ini ./
COPY app ./app
COPY frontend ./frontend
COPY migrations ./migrations
RUN useradd --create-home --uid 10001 app && mkdir /data /logs && chown app:app /data /logs
USER app
EXPOSE 8000
CMD ["sh", "-c", ".venv/bin/alembic upgrade head && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000"]
