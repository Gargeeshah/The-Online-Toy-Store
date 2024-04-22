import requests
import random
import time
from dotenv import load_dotenv
import os
import json

# Load environment variables from .env file
load_dotenv()

class ToyStoreClient:

    @staticmethod
    def run_session(total_query_time,total_buy_time):

        # Select a random product name from the list
        product_name = random.choice(TOY_NAME_LIST)
        print("Query TOY: ", product_name)

        # Construct the URL to query the product information
        print("Query TOY: ", product_name)

        # Construct the URL to query the product information
        base_url = f'http://{host}:{port}'
        url = f'{base_url}/product/{product_name}'

        # Measure the start time of the query
        query_start_time = time.time()

        # Send a GET request to retrieve product information

        # Measure the start time of the query
        query_start_time = time.time()

        # Send a GET request to retrieve product information
        response = session.get(url)

        # Measure the end time of the query and calculate the time taken
        query_end_time = time.time()
        diff_query_time = query_end_time - query_start_time
        total_query_time += diff_query_time

        # Handle the response based on the status code
        if response.status_code != 200:
            print(response.json())
            print(response.json())
        else:
            data = response.json()
            print(data)
            nested_data = data.get('data')
            quantity = nested_data.get('quantity')
            prob = random.uniform(0, 1)
            quantity = nested_data.get('quantity')
            quant = random.choice(ORDER_LIST)

            # If the quantity is available and a random condition is met, place an order
            if quantity > 0 and random.random() <= prob:
                request_body = {
                    "name": product_name,
                    "quantity": quant
                }
                print("Order request: ", request_body)

                # Convert the request body to JSON format
                print("Order request: ", request_body)

                # Convert the request body to JSON format
                request_body_json = json.dumps(request_body)

                # Construct the URL to place an order

                # Construct the URL to place an order
                url = f'{base_url}/orders'
                post_start_time = time.time()
                response = session.post(url, data=request_body_json)
                post_end_time = time.time()
                diff_post_time = post_end_time - post_start_time
                total_buy_time += diff_post_time

                print(response.json())  

        return  total_query_time,total_buy_time   

if __name__ == "__main__":
    host = os.getenv('host')
    # host = '128.119.243.177'
    port = os.getenv('frontend_port')  # the host and port of the frontend server


    # Create a session for making HTTP requests
    session = requests.Session()
    
    # Initialize variables to track total query time and total buy time
    total_query_time = 0
    total_buy_time = 0 

    # Define lists of toy names and order quantities ,"Book","Bear","Tux","Shark"
    TOY_NAME_LIST = ["Tux", "Dolphin", "Whale", "Python", "Elephant","Fox"]
    ORDER_LIST = [100,50,2,200,32,50,11,33,5,66,90,1000,22,1,12,99]

    # Run the session multiple times
    for r in range(10):  
        print("Request: ",r)
        time.sleep(1)  # Wait for 1 second before each session
        total_query_time,total_buy_time = ToyStoreClient.run_session(total_query_time,total_buy_time)
    
    print("total_query_time: ",total_query_time)
    print("total_buy_time: ",total_buy_time)
