#!/bin/bash

# Change directory to Catalog and run catalog.py
echo "Running catalog.py"
cd Catalog
python3 catalog.py &

# Change directory to Order and run run-replicas.sh
echo "Running order replicas"
cd ../Order
./run-replicas.sh &

sleep 5
# Change directory to Frontend-Service and run frontend-service.py
echo "Running frontend-service.py"
cd ../Frontend-Service
python3 frontend-service.py 