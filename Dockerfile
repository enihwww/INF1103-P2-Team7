FROM python:3.11-slim
WORKDIR /app
COPY req.txt .
RUN pip install --no-cache-dir -r req.txt

COPY . .
# Let the GUI accept connections from outside the container.
ENV CLUBFUND_HOST=0.0.0.0
EXPOSE 5000
CMD ["python","main.py"]
