FROM python:3.10.12

WORKDIR /app

# 將專案複製到容器中
COPY requirements.txt .

# 安裝必要的套件
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY ./app ./app

EXPOSE 8080
CMD uvicorn app.main:app --host=0.0.0.0 --port=$PORT