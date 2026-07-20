FROM python:3.13-slim

# Create a non-root user and group
RUN addgroup --system appgroup && adduser --system --group appuser

WORKDIR /app


# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . /app/

# Create the data directory and give ownership ONLY to the non-root user
RUN mkdir -p /app/data && chown -R appuser:appgroup /app

# Drop root privileges!
USER appuser

# Run the server using the dynamic $PORT provided by Cloud Run
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]