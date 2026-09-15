FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 DATABASE_URL=sqlite:////data/nova.db
WORKDIR /app
COPY requirements.lock ./
RUN pip install -r requirements.lock && useradd --uid 10001 --create-home nova && mkdir /data && chown nova:nova /data
COPY app.py ./
COPY nova_core ./nova_core
COPY migrations ./migrations
USER nova
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
