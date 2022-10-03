# docker build ./frontend -t dmw2151/astro_frontend
FROM node:18.10.0-slim

COPY ./ /frontend/
WORKDIR /frontend/src/

RUN cd /frontend/src/ && npm install http-server -g && npm install

EXPOSE 8000

ENTRYPOINT http-server . -p 8000