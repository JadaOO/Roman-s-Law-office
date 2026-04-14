# Law office Streamlit app (calendar, legal research, billing, etc.)
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# crewai / scientific stack may need compilers for some wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY db /app/db

RUN pip install --upgrade pip setuptools wheel \
    && pip install "/app" \
    && pip install beautifulsoup4 fpdf2 python-dotenv sendgrid

EXPOSE 8501

CMD ["streamlit", "run", "src/app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true"]
