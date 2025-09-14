# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (if any of your Python packages require compilation)
# For api_service, numpy is not directly used, so build-essential might not be strictly needed
# but it's good practice to include if you have any C-extension heavy libraries.
# For this specific api_service.py, it doesn't seem to use numpy directly,
# so these might not be strictly necessary, but won't hurt.
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    # libatlas-base-dev \ # Only if numpy is used for heavy computation
    # gfortran \          # Only if fortran libraries are used
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code (including main.py and the static folder)
COPY . .

# Expose the port that the application will listen on
ENV PORT 8080

# Run the application using Uvicorn
# Assuming api_service.py is renamed to main.py and the FastAPI app is named app_fastapi
CMD ["uvicorn", "main:app_fastapi", "--host", "0.0.0.0", "--port", "8080"]