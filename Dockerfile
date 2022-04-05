ARG IMAGE_NAME=library/python
ARG IMAGE_TAG=3.10-slim
FROM ${IMAGE_NAME}:${IMAGE_TAG}

COPY ./processTimeTrackingEntries.py /
RUN pip install --no-cache-dir python-dateutil togglwrapper jira

CMD ["python", "/processTimeTrackingEntries.py", "-c", "/config/config.ini"]