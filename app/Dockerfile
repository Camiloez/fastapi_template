FROM python:3.11

# Set working directory
WORKDIR /usr/src


# Install Poetry
RUN pip install poetry==1.8.3

COPY pyproject.toml poetry.lock /usr/src

# Install python dependencies
RUN poetry install

COPY app/ /usr/src/app

