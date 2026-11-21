FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY portal ./

CMD ["sh", "-c", "streamlit run Home.py --server.port ${PORTAL_PORT:-8501} --server.address 0.0.0.0 --browser.gatherUsageStats false"]
