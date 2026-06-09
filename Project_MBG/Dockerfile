FROM python:3.11.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7860 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 8000 & streamlit run app.py --server.port 7860 --server.address 0.0.0.0"]
