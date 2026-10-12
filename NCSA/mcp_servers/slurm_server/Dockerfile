FROM python:3.12-slim
WORKDIR /app

# accounts on Delta is a Perl script; keep a minimal interpreter in-image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends perl \
    && rm -rf /var/lib/apt/lists/*

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
ENV PORT=8001
ENV CONFIG_FILE=config.json
ENV LD_LIBRARY_PATH=/usr/lib64/slurm:/usr/lib64:${LD_LIBRARY_PATH}

EXPOSE 8001
ENTRYPOINT ["./entrypoint.sh"]
