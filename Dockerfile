FROM python:3.11-slim

WORKDIR /app

# 필요한 패키지 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 전체 소스코드 복사
COPY . .

# Render가 열어주는 포트를 감지하여 NiceGUI 실행
EXPOSE 8080
CMD ["python", "main.py"]