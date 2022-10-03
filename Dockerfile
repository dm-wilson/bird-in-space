FROM python:3.10-slim

COPY ./src /src

RUN python3 -m pip install -r ./src/requirements.txt
