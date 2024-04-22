#!/bin/bash

# Run the instances of the Python client script in the background
cd ../Client
python3 client.py &
python3 client.py &
python3 client.py &
python3 client.py &
python3 client.py &

# Optionally, you can wait for all processes to finish
wait
