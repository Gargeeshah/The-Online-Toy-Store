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
    port = os.getenv('frontend_port')  # the host and port of the frontend server
    session = requests.Session()
    order = {}
    order["Rabbit"] = -20
    order["Fox"] = 100
    order["Dolphin"] = -2
    order["Python"] = 50
    order["Tux"] = 1000
    order["Whale"] = 0
    order["Monkey"] = 22
    
    for key,value in order.items():
        time.sleep(1)
        product_url = f'http://{host}:{port}/product/{key}'
        print("GET: URL: ",product_url)
        response = session.get(product_url)
        print(response.json()) 

        order_url = f'http://{host}:{port}/orders'
        request_body = {
            "name": key,
            "quantity": value
        }
        print("POST request: ",request_body)
        request_body_json = json.dumps(request_body)
        response = session.post(order_url,data=request_body_json)
        print(response.json())  
        