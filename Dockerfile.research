FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 NOVA_DB=/data/nova-research-0.1.1.db
RUN useradd --uid 10001 --create-home nova && mkdir -p /app /data && chown -R nova:nova /app /data
WORKDIR /app
COPY --chown=nova:nova nova_research_backend.py /app/nova_research_backend.py
USER nova
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/health', timeout=4)"
CMD ["python", "nova_research_backend.py"]
