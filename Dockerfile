FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN python -m pip install --upgrade pip && \
    grep -vE "^(pywin32|pywin32-ctypes)==" /app/requirements.txt > /tmp/requirements-linux.txt && \
    python -m pip install -r /tmp/requirements-linux.txt

COPY . /app

EXPOSE 8000

CMD ["python", "api.py"]
