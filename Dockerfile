FROM python:3.13.0a3-bullseye

# Pre reqs
RUN apt update
RUN apt install -y curl
RUN pip3 install poetry

# Set up our source dir
WORKDIR /opt/slackbot
COPY . .
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi

# Run slackbot as entrypoint
ENTRYPOINT ["python3", "/opt/slackbot/snyk_slackbot/main.py"]