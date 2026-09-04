# syntax=docker/dockerfile:1
# Self-hosted image for skiplum-apps-1 (see skiplum/internal/infra/apps-server).
# Community Cloud keeps deploying from requirements.txt; this file is inert there.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# Pinned to the combination that ran on Streamlit Community Cloud 2026-06-22
# (Python 3.13 / streamlit 1.58.0 / pandas 3.0.3 / ifcopenshell 0.8.5) and
# matches the versions the June coloring fixes were verified against.
RUN pip install streamlit==1.58.0 pandas==3.0.3 ifcopenshell==0.8.5

COPY app.py ./
COPY .streamlit ./.streamlit

RUN useradd -m app && chown -R app /app
USER app

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3).read()==b'ok' else 1)"

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
