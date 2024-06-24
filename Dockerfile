FROM python:3.10-alpine
WORKDIR /helper_bot
COPY . /helper_bot
RUN pip3 install --upgrade setuptools
RUN pip3 install -r requirements.txt
RUN chmod 755 .
CMD ["python", "main.py"]