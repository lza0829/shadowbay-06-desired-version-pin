FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
ENV 数据目录=/data 预置目录=/fixtures
EXPOSE 12100
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "12100"]
