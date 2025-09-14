# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install any needed packages specified in requirements.txt
# Copy requirements.txt first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port that the application will listen on
# Cloud Run expects the application to listen on the port specified by the PORT environment variable,
# which defaults to 8080 if not set.
ENV PORT 8080

# Run the application using Uvicorn
# The command to run your FastAPI app: uvicorn <your_python_file_name>:app --host 0.0.0.0 --port $PORT
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]