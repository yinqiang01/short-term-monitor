FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 TZ=Asia/Shanghai
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ libffi-dev tzdata \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# 先装基础依赖，再装全部，失败立即报错
RUN pip install --upgrade pip && \
    pip install numpy pandas pyyaml python-dotenv loguru requests flask flask-cors apscheduler && \
    pip install akshare && \
    pip install -r requirements.txt
COPY . .
RUN mkdir -p logs data
EXPOSE 8080
CMD ["python", "-m", "src.main"]
