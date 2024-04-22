import requests
import random
import time
from dotenv import load_dotenv
import os
import json

# Load environment variables from .env file
load_dotenv()


if __name__ == "__main__":
    host = os.getenv('host')
    port = os.getenv('order_PORT')  # the host and port of the Order serviceS
    session = requests.Session()
    order = {}
    order["Rabbit"] = -20
    order["Fox"] = 100
    order["Dolphin"] = -2
    order["Python"] = 50
    order["Tux"] = 1000
    order["Whale"] = 0
    order["Monkey"] = 22
    order["Elephant"] = 22.3
    order["Book"] = 12
    
    for key,value in order.items():
        time.sleep(1)
        base_url = f'http://{host}:{port}/orders'
        request_body = {
            "name": key,
            "quantity": value
        }
        print(request_body)
        response = session.post(base_url,data=request_body)
        if response.status_code == 200:
            json_response = response.json()
            print(json_response)
        else:
            if response.status_code == 404:
                    resp_message = f"Sorry {key} is not found."
            elif response.status_code == 400:
                resp_message = f"Sorry {key} is out of stock or invalid quantity"
            else:    
                resp_message = "An error occurred while buying the product"
            error_response = {
            "error": {
                "code": response.status_code,
                "message": resp_message
                }
            }
            print(error_response)   