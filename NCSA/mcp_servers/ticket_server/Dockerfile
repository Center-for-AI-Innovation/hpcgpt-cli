FROM python:3.12-slim
WORKDIR /app

COPY ./requirements.txt ./requirements.txt
COPY ./src ./src
COPY ./server.py ./server.py
COPY ./entrypoint.sh ./entrypoint.sh
COPY ./config.docker.json ./config.json
COPY ./fixtures ./fixtures

RUN pip install --no-cache-dir -r requirements.txt \
    && mkdir -p logs /data \
    && cp ./fixtures/clustered.json /data/clustered.json \
    && chmod -R ugo+rwX . /data \
    && chmod ugo+rx ./entrypoint.sh

ENV HOST_IP=0.0.0.0
ENV PORT=8004
ENV CONFIG_FILE=config.json

EXPOSE 8004
ENTRYPOINT ["./entrypoint.sh"]
