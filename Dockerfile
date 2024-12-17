FROM python:3.11-alpine

WORKDIR /depfuzzer/
ADD . /depfuzzer/

RUN pip install -r requirements.txt
RUN chmod +x main.py

ENTRYPOINT ["/depfuzzer/main.py"]
