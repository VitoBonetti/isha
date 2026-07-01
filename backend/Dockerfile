# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . /app/

# Expose the port FastAPI runs on (default is 8000, but we'll make it configurable)
EXPOSE 8000

# Run the app using Uvicorn (as listed in requirements [10])
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]