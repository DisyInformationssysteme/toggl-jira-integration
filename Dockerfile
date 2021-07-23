FROM library/alpine AS fetch-togglwrapper
RUN apk update && apk upgrade && \
    apk add --no-cache git
RUN git clone https://github.com/DisyInformationssysteme/togglwrapper.git /tmp/togglwrapper

FROM library/python:3.9-slim

COPY ./processTimeTrackingEntries.py /
COPY --from=fetch-togglwrapper /tmp/togglwrapper /tmp/togglwrapper
RUN cd /tmp/togglwrapper && python setup.py install
RUN pip install --no-cache-dir python-dateutil jira

CMD ["python", "/processTimeTrackingEntries.py", "-c", "/config/config.ini"]