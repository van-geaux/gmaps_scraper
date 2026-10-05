FROM python:3.12-alpine

RUN apk add --no-cache curl
COPY gateway.py /opt/gateway.py

ENTRYPOINT ["python", "/opt/gateway.py"]
