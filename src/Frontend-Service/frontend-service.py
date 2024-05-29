from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import json
from dotenv import load_dotenv
import os
import requests
from urllib.parse import parse_qs
from contextlib import contextmanager
from threading  import Lock
from collections import OrderedDict

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

    # ___________________________________________________________________
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
        try:
            self.r_acquire()
            yield
        finally:
            self.r_release()

    # ___________________________________________________________________
    # Writing methods.

    def w_acquire(self):
        self.w_lock.acquire()

    def w_release(self):
        self.w_lock.release()

    @contextmanager
    def w_locked(self):
        try:
            self.w_acquire()
            yield
        finally:
            self.w_release()


class Node:
    def __init__(self, key,val):
        self.key,self.val = key, val
        self.prev = self.next = None

class LRUCache(object):

    def __init__(self,capacity):
        """
        :type capacity: int
        """
        self.cap = capacity
        self.cache = OrderedDict()
        self.left,self.right = Node(0,0),Node(0,0)
        self.left.next,self.right.prev = self.right,self.left
        self.rwlock = RWLock()

    def remove(self, node):
        nxt,prev = node.next,node.prev
        prev.next,nxt.prev = nxt,prev 
    
    def insert(self,node):
        prev,nxt = self.right.prev,self.right
        prev.next = nxt.prev = node
        
        node.prev = prev
        node.next = nxt
       
    def get(self, key):
        """
        Return:
            returns -1 if the key is not found
        """
        if key in self.cache:
            # Remove the item before putting it into the cache so the item can be the newest in the cache
    
            self.remove(self.cache[key])
            self.insert(self.cache[key])
            return self.cache[key].val
        return -1
    
    def put(self, key, value):
        print("Capacity: ",len(self.cache))
        with self.rwlock.w_locked():
            if key in self.cache:
                # Pop the item before putting it into the cache
                self.remove(self.cache[key])
            
            self.cache[key] = Node(key,value)
            self.insert(self.cache[key])
        
            if len(self.cache) > int(self.cap):
                print("exceeds cap")
                print("Before remove: ",len(self.cache))
                lru = self.left.next
                self.remove(lru)
                del self.cache[lru.key]
                print("After remove: ",len(self.cache))
            
    
    def pop(self, key):
        """
        Return:
            returns 1 if operation succeeds, -1 if the key is not found
        """
        with self.rwlock.w_locked():
            if key not in self.cache:
                return -1
            else:
                self.remove(self.cache[key])
                del self.cache[key]
                return 1

def leader_selection(server):
    print("LEADER SELECTION")
    # Try to connect to an order server, starting from the highest id
    server.leader_id = None
    while server.leader_id is None:
    # Try each order service until a leader is found
        for order_id in server.sorted_order_ids: 
            #Create the order address
            order_port = os.getenv(f"ORDER_PORT_{order_id}")
            order_host = os.getenv(f"ORDER_HOST_{order_id}")
            order_address = f"http://{order_host}:{order_port}"
            # Ping the order service
            print(f'{order_address}/ping')
            try:
                # Ping the server and see if there is a receipt
                response = requests.get(f"{order_address}/ping",params={'message': 'Ping'})
                print(response.json())

                # If response '200', pick it as the leader
                if response.status_code == 200:
                    server.leader_id = order_id
                    data = {'leader_id': server.leader_id, 'message': 'You win'}
                    response = requests.post(f"{order_address}/leaderselection",data=data)
                    print("Response from leader:",response.json())


                    break
            except:
                    continue
            
    if server.leader_id:   # Notify all replicas that a leader has been selected     
        for replica_id in server.sorted_order_ids:

                    if replica_id!=order_id:
                        replica_port = os.getenv(f"ORDER_PORT_{replica_id}")
                        replica_host = os.getenv(f"ORDER_HOST_{replica_id}")
                        replica_address = f"http://{replica_host}:{replica_port}"
                        # If no response, just continue      
                        try:
                            response = requests.post(f"{replica_address}/inform_replica", data={'leader_id': server.leader_id})
                            print("Response from replicas",response.json()) 
                        except:
                            continue  # Try the next replica


# Define a toy request handler class that handles HTTP GET and POST requests
class FrontEndRequestHandler(BaseHTTPRequestHandler):

    # Handle a GET request.
    def do_GET(self):
        self.protocol_version = "HTTP/1.1" 

        # Check the validity of URL
        if self.path.startswith("/product"):

            # Extract the toy name from the URL query parameter
            product_name = self.path.split("/")[-1]  
            
            # Check whether the request can be served from the cache
            if self.server.cache_or_not == True:
                cache_item = self.server.lrucache.get(product_name)
            else:
                cache_item = -1
            
            # If it's a cache miss
            if cache_item == -1:
                response = self.server.front_end_service.query_product(product_name) 
            # If it's a cache hit
            else:
                response = cache_item 

        # Query existing orders
        elif self.path.startswith("/orders"):

            # Extract the order number from the URL
            order_number = self.path.split("/")[-1]  
                    
            # Forward the request to the order server
            response = self.server.front_end_service.query_order_number(self.server,order_number)
            
        # The URL of the GET request is invalid -> raise error 404 
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            response = {"error": {"code": 404, "message": f"invalid URL: {self.path}"}}
            
        self.send_custom_response(response)  

    # override the default do_POST() method
    def do_POST(self):

        self.protocol_version = "HTTP/1.1"

        # Handle a POST request.
        if self.path.startswith("/orders"):
            
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            request_body = json.loads(post_data)

            # Forward the request to the order server
            response = self.server.front_end_service.place_order(self.server,request_body)  

        # Invalidation request from Catalog
        elif self.path.startswith("/invalidate?toy="):
            
            if self.server.cache_or_not == True:
                toy_name = self.path.split('=')[-1]
                self.server.lrucache.pop(toy_name)
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                response = "The item was successfully removed from the cache"

        else:
            # The URL of the POST request does not start wtih "/orders" -> raise error 404 
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            response = {
                "error": {
                    "code": 404, 
                    "message": f"invalid URL: {self.path}"
                }
            }
            
        self.send_custom_response(response)  

    def send_custom_response(self, response):
        if "error" in response:
            self.send_response(
                response["error"]["code"]
            ) 
        else:
            self.send_response(200)  
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps(response).encode("utf-8")
        )  


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass

# Define a threaded HTTP server that allows for multiple concurrent requests.
class FrontEndService(ThreadedHTTPServer):
     # Override the init function to save metadata in the server
    def __init__(self, port, catalog_address, order_ids,cache_s,c):

        super().__init__(("", port), FrontEndRequestHandler)
        self.front_end_service = self  
        self.catalog_address = catalog_address  
        self.order_ids = order_ids

        self.sorted_order_ids = sorted(self.order_ids, reverse=True)
        #order_host = os.getenv("ORDER_HOST")   #Needs to be changed 

        self.leader_id = None
       
        # Read-write lock
        self.rwlock = RWLock()

        # Initialize cache
        self.cache_or_not = c
        print("Cache request: ",self.cache_or_not)
        if self.cache_or_not == True:
            self.lrucache = LRUCache(cache_s)

    # Function to query toy
    def query_product(self, product_name):
        
         # Forward the request to the catalog server
        catalog_url = f"{self.catalog_address}/product/{product_name}"
        response = requests.get(catalog_url)

        # Check the response 
        if response.status_code == 200:
            # Update the cache (if cache is used)
            json_response = response.json()
            if self.cache_or_not == True:
                response = self.lrucache.put(product_name,json_response)
            return json_response
        
        # If the toy name does not exist in the catalog
        elif response.status_code == 404:
            resp_message = "Toy not found"
            error_response = {"error": {"code": response.status_code, "message": resp_message}}
            return error_response  

        # If the URL is invalid
        else:
            raise RuntimeError("Frontend should check the URL for the order service")
        
    
    # Function to query the order number
    def query_order_number(self,server,order_number):

        response = None
        while response == None:
            try:

                print("self.server.leader_id: ",server.leader_id)
                order_port = os.getenv(f"ORDER_PORT_{server.leader_id}")
                order_host = os.getenv(f"ORDER_HOST_{server.leader_id}")
                leader_host, leader_port = order_host, order_port 
                # Forward the request to the order server
                order_url =  f"http://{leader_host}:{leader_port}/orders/{order_number}"
                print("order_query_url: ",order_url)
                response = requests.get(order_url)

            except requests.exceptions.RequestException as e:
                # Passive health check
                print(f'An request exception occurs: {e}. Re-select a leader.')
                with server.rwlock.w_locked():
                    leader_selection(server)

        # If the order number exists
        if response.status_code == 200:
            json_response = response.json()
            return json_response  
        
        # If the order number does not exist
        elif response.status_code == 400:
            resp_message = "Order number doesn't exist"
            error_response = {"error": {"code": response.status_code, "message": resp_message}}
            return error_response 
        
        # If the URL is invalid
        else:
            raise RuntimeError("Frontend should check the URL for the order service")

    # Function to place an order
    def place_order(self, server,order_data):

        response = None
        while response == None:
            try:

                print("self.server.leader_id: ",server.leader_id)
                order_port = os.getenv(f"ORDER_PORT_{server.leader_id}")
                order_host = os.getenv(f"ORDER_HOST_{server.leader_id}")
                leader_host, leader_port = order_host, order_port 
                order_url =  f"http://{leader_host}:{leader_port}/orders"
                print("order_buy_url", order_url)
                response = requests.post(order_url, data=order_data)
                
            except requests.exceptions.RequestException as e:
                # Passive health check
                print(f'An request exception occurs: {e}. Re-select a leader.')
                with server.rwlock.w_locked():
                    leader_selection(server)
        
        #Order successfully
        if response.status_code == 200:
            json_response = response.json()
            return json_response 
        
        #Invalid Quantity 
        elif response.status_code == 400:
            resp_message = (f"Sorry {order_data['name']} is out of stock or invalid quantity")
            error_response = {"error": {"code": response.status_code, "message": resp_message}}
            return error_response  
        
        # If the URL is invalid
        else:
            raise RuntimeError("Frontend should check the URL and the requested quantity for the order service")


if __name__ == "__main__":

    frontend_port = int(os.getenv("frontend_port"))

    catalog_port = int(os.getenv("catalog_PORT"))
    catalog_host = os.getenv("catalog_host")
    catalog_service_address = f"http://{catalog_host}:{catalog_port}"

    order_ids = [
            int(os.getenv("ORDER_ID_1")),
            int(os.getenv("ORDER_ID_2")),
            int(os.getenv("ORDER_ID_3"))
        ]

    CACHE_SIZE =os.getenv("cache_size")
    CACHE = os.getenv("cache_include")
    # Convert the string value to a boolean
    CACHE = CACHE.lower() == 'true' 

    # Set up the threaded HTTP server with the given port and request handler.
    front_end_service = FrontEndService(
        port=frontend_port,
        catalog_address=catalog_service_address,
        order_ids=order_ids,
        cache_s = CACHE_SIZE,
        c = CACHE
    )
    # Select the leader order service
    leader_selection(front_end_service)

    print(f"Serving on port {frontend_port}")

    # Start serving requests.
    front_end_service.serve_forever()  
