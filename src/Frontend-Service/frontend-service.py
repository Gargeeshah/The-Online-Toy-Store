from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import json
from dotenv import load_dotenv
import os
import socket
import requests

# Load environment variables from .env file
load_dotenv()

class FrontEndRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Handle GET requests
        self.protocol_version = "HTTP/1.1"
        product_name = self.path.split('/')[-1]  # Extract product name from URL
        response = self.server.front_end_service.query_product(product_name)  # Query product from the front-end service
        self.send_custom_response(response)  # Send custom response based on the query result

    def do_POST(self):
        # Handle POST requests
        self.protocol_version = "HTTP/1.1"
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        request_body = json.loads(post_data)
        response = self.server.front_end_service.place_order(request_body)  # Place an order through the front-end service
        self.send_custom_response(response)  # Send custom response based on the order result

    def send_custom_response(self, response):
        # Send custom HTTP response with appropriate headers and content
        if 'error' in response:
            self.send_response(response['error']['code'])  # Send error code if an error occurred
        else:
            self.send_response(200)  # Send success code for successful requests
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))  # Encode and send JSON response
   
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass  

class FrontEndService(ThreadedHTTPServer):
    def __init__(self, port, catalog_address, order_address):
        # Initialize the front-end service with catalog and order service addresses
        super().__init__(('', port), FrontEndRequestHandler)
        self.front_end_service = self  # Reference to the front-end service itself
        self.catalog_address = catalog_address  # Address of the catalog service
        self.order_address = order_address  # Address of the order service

    def query_product(self, product_name):
        # Send a GET request to the catalog service to query a product
        catalog_url = f'{self.catalog_address}/product/{product_name}'
        response = requests.get(catalog_url)
        if response.status_code == 200:
            json_response = response.json()
            return json_response  # Return JSON response if successful
        else:
            if response.status_code == 404:
                resp_message = "Product not found"
            else:
                resp_message = "An error occurred while querying the product"
            error_response = {
                "error": {
                    "code": response.status_code,
                    "message": resp_message
                }
            }
            return error_response  # Return error response if unsuccessful

    def place_order(self, order_data):
        # Send a POST request to the order service to place an order
        order_url = f'{self.order_address}/orders'
        print("order_url",order_url )
        response = requests.post(order_url, data=order_data)
        if response.status_code == 200:
            json_response = response.json()
            return json_response  # Return JSON response if successful
        else:
            if response.status_code == 404:
                resp_message = f"Sorry {order_data['name']} is not found."
            elif response.status_code == 400:
                resp_message = f"Sorry {order_data['name']} is out of stock or invalid quantity"
            else:
                resp_message = "An error occurred while buying the product"
            error_response = {
                "error": {
                    "code": response.status_code,
                    "message": resp_message
                }
            }
            return error_response  # Return error response if unsuccessful

if __name__ == "__main__":
    load_dotenv()
    frontend_port = int(os.getenv('frontend_port'))
    catalog_port = int(os.getenv('catalog_PORT'))
    catalog_host = os.getenv('catalog_host')
    catalog_service_address = f"http://{catalog_host}:{catalog_port}"
    order_port = int(os.getenv('order_PORT'))
    order_host = os.getenv('order_host')
    order_service_address = f"http://{order_host}:{order_port}"

    # Initialize the front-end service with necessary configurations
    front_end_service = FrontEndService(port=frontend_port, catalog_address=catalog_service_address, order_address=order_service_address)
    front_end_service.serve_forever()  # Start serving HTTP requests indefinitely