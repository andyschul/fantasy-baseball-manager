FROM python:3.9-slim-buster

WORKDIR /usr/src/app

# Update the repository sources list and install firefox
RUN apt-get update && apt-get install -y \
    firefox-esr

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "./app.py"]
