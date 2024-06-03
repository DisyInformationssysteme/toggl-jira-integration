ARG IMAGE_NAME=library/python
ARG IMAGE_TAG=3.12-slim
FROM ${IMAGE_NAME}:${IMAGE_TAG} AS builder
RUN apt update -y && apt upgrade -y && apt install -y git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir python-dateutil jira
RUN pip install git+https://github.com/Zapgram/togglwrapper

FROM ${IMAGE_NAME}:${IMAGE_TAG}
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY ./processTimeTrackingEntries.py /

CMD ["python", "/processTimeTrackingEntries.py", "-c", "/config/config.ini"]