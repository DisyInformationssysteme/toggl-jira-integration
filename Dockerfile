ARG IMAGE_NAME=library/python
ARG IMAGE_TAG=3.12-slim
FROM ${IMAGE_NAME}:${IMAGE_TAG}

COPY ./processTimeTrackingEntries.py /
RUN pip install --no-cache-dir python-dateutil jira
RUN pip install git+https://github.com/Zapgram/togglwrapper

CMD ["python", "/processTimeTrackingEntries.py", "-c", "/config/config.ini"]