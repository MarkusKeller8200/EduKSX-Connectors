FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY api.json .
COPY escola_api ./escola_api
EXPOSE 8080
# Zugangsdaten und Schalter nur über Umgebungsvariablen (--env-file), nie ins Image
CMD ["uvicorn", "escola_api.app:app", "--host", "0.0.0.0", "--port", "8080"]
