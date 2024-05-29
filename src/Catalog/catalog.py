import json
import http.server
import os
from dotenv import load_dotenv
from http.server import HTTPServer
from socketserver import ThreadingMixIn
from contextlib import contextmanager
from threading import Lock,Thread
import csv
import socket
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
import pandas as pd
import time
import requests
import warnings

# Suppress the specific warning about Pyarrow not being installed
warnings.simplefilter("ignore", category=DeprecationWarning)

# Load environment variables from .env file
load_dotenv()

class RWLock(object):
    """RWLock class based on https://gist.github.com/tylerneylon/a7ff6017b7a1f9a506cf75aa23eacfd6
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

#Catalog Server class for managing toy catalog and serving HTTP requests.
class CatalogServer:

    #Initialize CatalogServer with the specified port and CSV file path.
    def __init__(self, PORT, csv_file,cache : bool):
        self.port = int(PORT)
        self.csv_file = csv_file
        # Initialize the catalog as an empty dictionary
        self.catalog = {}  
         # Initialize the read-write lock
        self.rwlock = RWLock() 
        self.cache = cache
        
        self.restock_interval = 10  # Restock interval in seconds
        self.restock_thread = Thread(target=self.restock_toys_thread)
        self.restock_thread.daemon = True  # Daemonize the thread to automatically terminate when the main thread exits
        self.restock_thread.start()  # Start the restocking thread

    #Define a function to initialize a catalog with some initial data
    def init_catalog(self):
        with self.rwlock.w_locked():
            # Open the file in write mode and write the initial data to the catalog in memory
            with open(self.csv_file, "r") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    product_name = row["Toy"]
                    price = float(row["Price"])
                    quantity = int(row["Quantity"])
                    self.catalog[product_name] = {"Price": price, "Quantity": quantity}
    
    #Lookup a toy in the catalog by name.
    def lookup(self, toy_name):
        # Read from hashmap and return the data if the toyname is valid
        with self.rwlock.r_locked():
            if toy_name in self.catalog:
                return True
            return -1

    # Define a function to perform Order, returning the value indicating the result of the trade
    def order(self, toy_name, quantity):
        with self.rwlock.w_locked():
            # Check if order will occur
            if toy_name in self.catalog and self.catalog[toy_name]["Quantity"] >= quantity:
                self.catalog[toy_name]["Quantity"] -= quantity
                # Update the catalog CSV file after ordering
                self.update()  
                return 1
            return -1

    #Update the CSV file with the current catalog data.
    def update(self):
        # Reads the data
        df = pd.read_csv(self.csv_file)
        for toy, info in self.catalog.items():
            if toy in df['Toy'].values:
                df.loc[df['Toy'] == toy, 'Quantity'] = info['Quantity']
                df.loc[df['Toy'] == toy, 'Price'] = info['Price']
        df.to_csv(self.csv_file, index=False)

    # Method for periodic restocking of toys.
    def restock_toys_thread(self):
        while True:
            time.sleep(self.restock_interval)
            with self.rwlock.w_locked():
                for toy, info in self.catalog.items():
                        # Restock quantity
                        if self.catalog[toy]["Quantity"] <= 10:
                            self.catalog[toy]["Quantity"] += 100  
                            print("cache val: ", cache)
                            print("self.cache: ",type(self.cache))
                            if self.cache == True:
                                # Send an invalidation request to the frontend
                                self.invalidation_request(toy)
                       
                            # Update the catalog CSV file
                            self.update()  

    def invalidation_request(self, toy):
        request_url = f'http://{frontend_host}:{frontend_port}'
        url = f'{request_url}/invalidate?toy={toy}'
        frontend_response = requests.post(url)
        if frontend_response.status_code != 200:
            raise RuntimeError('Problematic response to the invalidation request')  
                    
    # Define a class to handle HTTP requests for the stock catalog
    def start_server(self):
        class CatalogRequestHandler(http.server.BaseHTTPRequestHandler):

            # Handle GET requests from both the frontend
            def do_GET(self):

                # If the request is for toy lookup
                if self.path.startswith("/product"):

                    # Parse the toy name from the request URL
                    toy_name = self.path.split("/")[-1]
                    # Look up the toy in the catalog
                    result = self.server.catalog_server.lookup(toy_name)
                    
                    # If the toy is found, return its data as a JSON response
                    if result == 1:
                        self.send_response(200)
                        self.send_header("Content-type", "application/json")
                        self.end_headers()
                        response = {"data": {"name": toy_name, "price": self.server.catalog_server.catalog[toy_name]["Price"], "quantity": self.server.catalog_server.catalog[toy_name]["Quantity"]}}
                        self.wfile.write(json.dumps(response).encode())
                        
                    # If the toy is not found, return an error response
                    else:
                        self.send_response(404)
                        self.send_header("Content-type", "text/plain")
                        self.end_headers()
                        
                # If the request is not for toy lookup, delegate to the base class
                else:
                    raise RuntimeError(f'Invalid URL: {self.path}') 
                    
            # Handle POST requests from the order service
            def do_POST(self):

                # Check the validity of URL
                if self.path.startswith("/orders"):
                    result = self.path.split("/")

                    # Parse the request to get the toy name, quantity
                    toy_n = result[2]
                    quantity_of_toy = result[3]

                    # Order the specified toy according to the request
                    result = self.server.catalog_server.order(toy_n, int(float(quantity_of_toy)))

                    # Send the appropriate response based on the result of the order operation
                    if result == 1:
                        self.send_response(200)
                        self.send_header("Content-type", "text/plain")
                        self.end_headers()
                        response = {"data": {"name": toy_n, "price":self.server.catalog_server.catalog[toy_n]["Price"] , "quantity": quantity_of_toy}}
                        self.wfile.write(json.dumps(response).encode())
                    else:
                        self.send_response(400)
                        self.send_header("Content-type", "text/plain")
                        self.end_headers()
                        
                else:
                    raise RuntimeError(f'Invalid URL: {self.path}') 
                    

                if cache == True:
                    # Send an invalidation request to the frontend
                    server.invalidation_request(toy_n)

        # Define a subclass of HTTPServer that uses threading to handle multiple requests concurrently
        class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
            # Override the init function to save metadata in the server
            def __init__(self, host_port_tuple, streamhandler):
                super().__init__(host_port_tuple, streamhandler)
                self.protocol_version = "HTTP/1.1"
           

        # Create a threaded HTTP server that listens on the specified port and handles requests with the CatalogRequestHandler class
        httpd = ThreadedHTTPServer(("", self.port), CatalogRequestHandler)
        httpd.catalog_server = self
        max_threads = multiprocessing.cpu_count()
        executor = ThreadPoolExecutor(max_workers=max_threads)
        httpd.executor = executor
        
        # Initiate the toys and prices in the catalog
        self.init_catalog()  

        # Start serving requests on the specified port
        print(f"Serving on port {self.port}")
        httpd.serve_forever()

if __name__ == "__main__":
    PORT = os.getenv("catalog_PORT")
    frontend_host = os.getenv("host")
    frontend_port = os.getenv("frontend_port")

    csv_file = os.getenv("catalog_csv_file")
    cache_include = os.getenv("cache_include")
    # Convert the string value to a boolean
    cache = cache_include.lower() == 'true' 
    print("CACHE: ",cache)

    server = CatalogServer(PORT, csv_file,cache)
    server.start_server()