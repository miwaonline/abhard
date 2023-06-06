FROM python:3.9-slim-buster
RUN pip install --no-cache-dir simplejson cherrypy requests pytz fdb pyyaml tzdata
RUN apt update && apt -y install libfbclient2
COPY . .
CMD [ "python", "src/abhard.py" ]
