FROM python:3.14-slim
WORKDIR /app
COPY ./requirements.txt ./requirements.txt
COPY ./src ./src
COPY ./server.py ./server.py
COPY ./entrypoint.sh ./entrypoint.sh
COPY ./config.json ./config.json
RUN pip install -r requirements.txt
RUN chmod -R ugo+rwX .
RUN chmod ugo+rx ./entrypoint.sh

ENV HOST_IP 0.0.0.0
ENV PORT 8000

ENTRYPOINT [ "./entrypoint.sh" ]
