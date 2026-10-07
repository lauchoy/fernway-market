FROM python:3.12.15-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY fernway ./fernway
RUN uv sync --frozen --no-dev \
    && useradd --create-home --uid 10001 app \
    && chown -R app:app /app
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["uvicorn", "fernway.main:app", "--host", "0.0.0.0", "--port", "8000"]
