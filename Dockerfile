# Gunakan Python 3.11 sebagai base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements dan install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY run.py .

# Buat file proxy_list.txt kosong yang akan di-mount
RUN touch proxy_list.txt

# Set environment variable dengan nilai default
ENV USER_ID=""

# Buat script entrypoint
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Set entrypoint
ENTRYPOINT ["./entrypoint.sh"] 