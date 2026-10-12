FROM python:3.12-slim
WORKDIR /app

COPY ./requirements.txt ./requirements.txt
COPY ./src ./src
COPY ./server.py ./server.py
COPY ./entrypoint.sh ./entrypoint.sh
COPY ./config.docker.json ./config.json

RUN pip install --no-cache-dir -r requirements.txt \
    && mkdir -p logs \
    && chmod -R ugo+rwX . \
    && chmod ugo+rx ./entrypoint.sh

ENV HOST_IP=0.0.0.0
ENV PORT=8003
ENV CONFIG_FILE=config.json

EXPOSE 8003
ENTRYPOINT ["./entrypoint.sh"]
