FROM python:3.8.1-slim-buster

COPY ./processTimeTrackingEntries.py /
RUN pip install --no-cache-dir python-dateutil togglwrapper jira

CMD ["python", "/processTimeTrackingEntries.py", "-c", "/config/config.ini"]