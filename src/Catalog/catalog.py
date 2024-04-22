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
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
from urllib.parse import parse_qs

# Load environment variables from .env file
load_dotenv()

class RWLock(object):
    """ RWLock class based on https://gist.github.com/tylerneylon/a7ff6017b7a1f9a506cf75aa23eacfd6
        Usage:
            my_obj_rwlock = RWLock()

            # When reading from my_obj:
            with my_obj_rwlock.r_locked():
                do_read_only_things_with(my_obj)

            # When writing to my_obj:
            with my_obj_rwlock.w_locked():
                mutate(my_obj)
    """
    def __init__(self):
        self.w_lock = Lock()
        self.num_r_lock = Lock()
        self.num_r = 0

    # _______________________
    # Reading methods.
    def r_acquire(self):
        self.num_r_lock.acquire()
        self.num_r += 1
        if self.num_r == 1:
            self.w_lock.acquire()
        self.num_r_lock.release()

    def r_release(self):
        assert self.num_r > 0
        self.num_r_lock.acquire()
        self.num_r -= 1
        if self.num_r == 0:
            self.w_lock.release()
        self.num_r_lock.release()

    @contextmanager
    def r_locked(self):
        self.r_acquire()
        try:
            yield
        finally:
            self.r_release()

    # _______________________
    # Writing methods.

    def w_acquire(self):
        self.w_lock.acquire()

    def w_release(self):
        self.w_lock.release()

    @contextmanager
    def w_locked(self):
        self.w_acquire()
        try:
            yield
        finally:
            self.w_release()



# Define a function to initialize a catalog file with some initial data    
def init_catalog(csv_file: str, catalog : dict, rwlock =  RWLock()): 
    with rwlock.w_locked():
        with open(csv_file, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                product_name = row['Toy Name']
                price = float(row['Price'])
                quantity = int(row['Quantity'])
                catalog[product_name] = {'price': price, 'quantity': quantity}

# Define a function to perform Lookp for the catalog_csv
def lookup(file_path: str, toy_name: str,rwlock: RWLock):
    """
    Return the price if the toy exists in the CSV file, or -1 if it doesn't.
    """
    rwlock = RWLock()
    # Open the CSV file and return the price if the toy name is valid
    with rwlock.r_locked():
        with open(file_path, 'r', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    if row['Toy Name'] == toy_name:
                        return True
                return -1  # Return -1 if toy name is not found in the CSV file


# Define a function to perform Order, returning an integer indicating the result of the order
def order(file_path: str, toy_name: str, quantity: int,rwlock = RWLock):
    """
    Return:
        1: The order succeeded.
        -1: The toy name was not found in the file.
        -2: The quantity is invalid.
        -3: The quantity exceeds the available stock quantity.
    """
    
    # Checks if the trading volume is equal to zero
    if quantity == 0 or quantity < 0 or type(quantity) == 'float':
        return -2
    
    # Reads the data
    with rwlock.r_locked():
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            data = [row for row in reader]

    for row in data:
        if row['Toy Name'] == toy_name:
            if quantity > int(row['Quantity']):
                return -3  # Quantity exceeds available toy quantity
            else:
                row['Quantity'] = int(row['Quantity']) - quantity
                with rwlock.w_locked():
                    with open(file_path, 'w', newline='', encoding='utf-8') as f:
                        catalog[toy_name]["quantity"] = row['Quantity']  
                        fieldnames = ['Toy Name', 'Quantity', 'Price']
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(data)
                  
                return 1
    return -1       

# Define a class to handle HTTP requests for the toy catalog
class CatalogRequestHandler(http.server.BaseHTTPRequestHandler):
    # Handle GET requests from both the frontend and the order service
    def do_GET(self):  
      
        # If the request is for query product
        if self.path.startswith("/product"):  
        # Parse the stock name from the request URL
            toy_name = self.path.split('/')[-1]
            # Look up the stock in the catalog
            result = lookup(csv_file, toy_name,self.server.rwlock)

            # If the stock is not found, return an error response
            if result == -1:
                self.send_response(404)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                response = {
                    "error": {
                        "code": 404,
                        "message": "Toy not found",
                    }
                }
                # If the toy is found, return its data as a JSON response
            else:
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                response = {
                    "data": {
                        "name": toy_name,
                        "price": catalog[toy_name]["price"],
                        "quantity": catalog[toy_name]["quantity"]
                    }
                }

            self.wfile.write(json.dumps(response).encode())
        # If the request is not for toy lookup, delegate to the base class
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            response = {
                "error": {
                    "code": 400, 
                    "message": "invalid request"
                }
            }

    def do_POST(self):

        # Parse the request body to get the toy name, quantity
        # If the request is for query product
        if self.path.startswith("/orders"):  
        # Parse the stock name from the request URL
            result = self.path.split('/')
            quantity_of_toy = result[3]
            print("result",result, "quantity",quantity_of_toy)
            result = order(os.getenv('catalog_csv_file'), result[2], int(float(quantity_of_toy)),self.server.rwlock)

            # Send the appropriate response based on the result of the trade operation
            if result == 1:
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
            
            elif result == -1:
                self.send_response(404)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
            
            else:
                self.send_response(400)
                self.send_header("Content-type", "text/plain")
                self.end_headers()

# Define a subclass of HTTPServer that uses threading to handle multiple requests concurrently
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    # Override the init function to save metadata in the server
    def __init__(self, host_port_tuple, streamhandler):
        super().__init__(host_port_tuple, streamhandler)
        self.rwlock = RWLock()
        self.protocol_version = 'HTTP/1.1'

    # Override the server_bind method to set a socket option for reusing the address
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)


def main(port,catalog_csv):

    httpd = ThreadedHTTPServer(("", port), CatalogRequestHandler)
    # Get the number of CPU cores and set the maximum number of threads in the thread pool
    max_threads = multiprocessing.cpu_count()
    
    # Initialize a ThreadPoolExecutor with the maximum number of threads
    executor = ThreadPoolExecutor(max_workers=max_threads)
    httpd.executer = executor  # Assign the executor to the server instance
    # Initiate the catalog
    init_catalog(catalog_csv,catalog,httpd.rwlock)

    # Start serving requests on the specified port
    print(f"Serving on port {port}")
    httpd.serve_forever()
   
if __name__ == "__main__":
    PORT = os.getenv('catalog_PORT') 
    
    csv_file = os.getenv('catalog_csv_file')
    catalog = {}
    main(int(PORT),csv_file)
    
