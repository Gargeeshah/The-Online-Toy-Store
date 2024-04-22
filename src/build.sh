#!/bin/bash

# Build Docker images
docker compose build

# Start Docker containers
docker compose up 

echo "Build and deployment completed."
