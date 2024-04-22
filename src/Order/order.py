import json
import http.server
import os
from dotenv import load_dotenv
from http.server import HTTPServer
from socketserver import ThreadingMixIn
from contextlib import contextmanager
from threading  import Lock
import csv
import socket
import requests
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs


# Load environment variables from .env file
load_dotenv()

order_number_lock = Lock()  # Create a Lock object for order_number


def update_csv(order_number,quant,product_name):
    if os.path.isfile(csv_file): 
        mode = 'a'  # Append mode to add new entries
    else:
        mode = 'w'  # Write mode to create a new file
    with open(csv_file, mode=mode, newline='') as file:
            fieldnames = ['Order Number', 'Toy Name', 'Quantity']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if mode == 'w':  # Write the header only if the file is newly created
                writer.writeheader()
            writer.writerow({'Order Number': order_number, 'Toy Name': product_name, 'Quantity': quant})


# Define a class to handle HTTP requests for the toy catalog
class OrderRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        global order_number  # Access the global order number variable
        global order_number_lock
        # Parse the request body to get the toy name, quantity
        content_length = int(self.headers["Content-Length"])
        request_body = self.rfile.read(content_length).decode()
        
        parsed_body = parse_qs(request_body)
        toy_name = parsed_body.get('name', [None])[0]
        quantity = float(parsed_body.get('quantity', [0])[0])
        
        #Forward the request to catalog
        base_url = f'http://{catalog_host}:{catalog_PORT}'
        url = f'{base_url}/orders/{toy_name}/{quantity}' 
        print("url--->",url)
        response = requests.post(url)
        
        if response.status_code == 200:
            #increment_order_number
            with order_number_lock:
                order_number += 1
                current_order_number = order_number
            update_csv(current_order_number,quantity,toy_name)
            self.send_response(200)
            self.send_header('Content-type','application/json')
            self.end_headers()
            response_data = {
            "data": {
                "order_number": current_order_number
                }
            }
            # Convert the response object to JSON format
            response_json = json.dumps(response_data)
            self.wfile.write(response_json.encode())
        
        elif response.status_code == 404:
            self.send_response(404)
            self.send_header('Content-type','application/json')
            self.end_headers()
            
        else:
            self.send_response(400)
            self.send_header('Content-type','application/json')
            self.end_headers()

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    # Override the init function to save metadata in the server
    def _init_(self, host_port_tuple, streamhandler):
        super()._init_(host_port_tuple, streamhandler)
        self.protocol_version = 'HTTP/1.1'    
    # Override the server_bind method to set a socket option for reusing the address
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)

def main(port,csv_file):
    httpd = ThreadedHTTPServer(("", port), OrderRequestHandler)
    # Get the number of CPU cores and set the maximum number of threads in the thread pool
    httpd.executer = ThreadPoolExecutor(max_workers=multiprocessing.cpu_count())  # Assign the executor to the server instance
   
    # Check if the CSV file exists

    global order_number
    # Check if the CSV file exists
    if os.path.isfile(csv_file):
        # Read the last order number from the CSV file
        with open(csv_file, 'r', newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                order_number = int(row['Order Number'])
    else:
        # Initialize order_number with 0 if the file doesn't exist
        order_number = 0
    # Start serving requests on the specified port
    print(f"Serving on port {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    # csv_file = 'order.csv'
    csv_file=os.getenv('order_csv_file')
    order_host = os.getenv('order_host')
    order_PORT = os.getenv('order_PORT') 
    catalog_host = os.getenv('catalog_host') 
    catalog_PORT = os.getenv('catalog_PORT')
    print("Catalog Host:",catalog_host, "Catalog Port", catalog_PORT)
    main(int(order_PORT),csv_file)