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
    port = os.getenv('catalog_PORT')  # the host and port of the Catalog service
    session = requests.Session()
    catalog_test = ["Tux","Fox", "Python", "Whale", "Elephant", "Dolphin","Monkey","Rabbit","Cheetah",""]
    for toy_name in catalog_test: 
        time.sleep(1)
        base_url = f'http://{host}:{port}'
        url = f'{base_url}/product/{toy_name}'
        print("URL: ",url)
        response = session.get(url)
        print(response.json()) 
       