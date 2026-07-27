FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir "litellm[proxy]"

# Copy backend code
COPY litellm /app/litellm

# Expose backend port
EXPOSE 4000

# Start proxy server
CMD ["litellm", "--port", "4000"]
