FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY app.py /app/app.py

EXPOSE 9443

CMD ["python", "/app/app.py"]
