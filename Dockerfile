# Use the official Python image
FROM python:3.11-slim

# Install system dependencies required for psycopg (PostgreSQL)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy dependencies file and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Expose application port
EXPOSE 8000

# Command to run the application
# (database migrations are better handled via a separate script or docker-compose)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
