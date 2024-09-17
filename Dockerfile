# Use the official Python image from the Docker Hub
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 8000 for the FastAPI app
EXPOSE 8000

# Run the FastAPI app using Uvicorn when the container starts
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]


# # Use the official Python image from the Docker Hub
# FROM python:3.9-slim

# # Set the working directory in the container
# WORKDIR /app

# # Copy the current directory contents into the container at /app
# COPY . /app

# # Install PostgreSQL development files
# RUN apt-get update && apt-get install -y \
#     libpq-dev \
#     && rm -rf /var/lib/apt/lists/*

# # Install any needed packages specified in requirements.txt
# RUN pip install --no-cache-dir -r requirements.txt

# # Expose port 8000 for the FastAPI app
# EXPOSE 8000

# # Run the FastAPI app using Uvicorn when the container starts
# CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]