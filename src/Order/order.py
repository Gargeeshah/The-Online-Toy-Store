import json
import http.server
import os
from dotenv import load_dotenv
from http.server import HTTPServer
from socketserver import ThreadingMixIn
from contextlib import contextmanager
from threading import Lock
import csv
import socket
import requests
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs,urlparse
import argparse
import time


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

#Initialize order from CSV.
def init_order(csv_file: str, order: dict):
        
        if os.path.isfile(csv_file):
            with open(csv_file, "r") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    order_n = row["Order Number"]
                    toyname = row["Toy Name"]
                    quantity = float(row["Quantity"])
                    order[order_n] = {"Toy Name": toyname, "Quantity": quantity}
        else:
            pass

#Update CSV file with new order data.
def update_csv(order_number, product_name, update_quantity):
    if os.path.isfile(csv_file):
        mode = "a" 
    else:
        mode = "w"  
    
    order[order_number] = {'Toy Name': product_name, 'Quantity': update_quantity}
    with open(csv_file, mode=mode, newline="") as file:
        fieldnames = ["Order Number", "Toy Name", "Quantity"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if mode == "w": 
            writer.writeheader()
        writer.writerow(
            {"Order Number": order_number, "Toy Name": product_name, "Quantity": update_quantity}
        )

#Lookup order number in the order dictionary.
def order_lookup(ordern):
    rwlock = RWLock()
    with rwlock.r_locked():
        if int(ordern) in order:        
                return 1
        return -1

def get_latest_order_number():
    if os.path.isfile(csv_file):
        with open(csv_file, "r", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                order_number = int(row["Order Number"])
            return order_number 
    return 0


def synchronize_replica(last_order_number, replica_address):
        rwlock = RWLock()
        # Synchronize the replica with other replicas to fetch missed orders
        try:
            missing_orders_url = f"{replica_address}/get_missed_orders/{last_order_number}"
            response = requests.get(missing_orders_url)
            if response.status_code == 200:
                # If successful, update replica's database with missed orders
                missed_orders = response.json()
                with rwlock.w_locked():
                    for order in missed_orders:
                        order_number = order['Order Number']
                        toy_name = order['Toy Name']
                        quantity = order['Quantity']
                        # print("Hello",csv_file, order_number, toy_name, quantity) 
                        update_csv(order_number, toy_name, quantity)
                print("Replica synchronized successfully")
            else:
                print("Failed to synchronize replica")
        except Exception as e:
            print(f"Error occurred while synchronizing replica: {e}")


def get_missed_orders_from_updated_replica(replica_last_order_number):
    missed_orders = []
    with open(csv_file, 'r', newline='') as file:
        reader = csv.DictReader(file)
        for row in reader:
            order_number = int(row['Order Number'])
            # Check if the order number is greater than the last order number
            if order_number > replica_last_order_number:
                missed_orders.append(row)
    return missed_orders 

#Order Server class for managing orders and serving HTTP requests.
class OrderRequestHandler(http.server.BaseHTTPRequestHandler):

    # Handle POST requests from the order service
    def do_POST(self):

        rwlock = RWLock()
        global order_number, leader_address
        
        """
        URL FLOW:
        Post /orders:
            /synchronize -> API first calls the synchronize api in the replicas servers, enabling any new replica to first synchronize itself with all other replicas, 
            by comparing its last order number with other replica's last order number fetched using /get_last_order_number. 
            If there is a mismatch in the last order numbers, using the /get_missed_orders, the other replicas would send the missed orders to the unsynchronized replica, 
            so that it can update it in its database.  
            /replicate_order ->  Once all the replicas are synchronized, the server can process new order requests at this endpoint. 
            Upon receiving an order request, the server first forwards the request to the catalog service to validate the order in terms of quantity. 
            If the order is valid, i.e, if the product is in stock, the server generates a new order number, updates its own database with the new order, 
            and then replicates the order to all other replicas by sending POST requests to their respective /replicate_order endpoints, where the replicas 
            update their own database.
        """
        # Check the validity of URL
        if self.path.startswith("/orders"):  
            if len(self.server.follower_addresses) > 0:
                try:
                    for follower_node_address in self.server.follower_addresses:
                            follower_url = f"{follower_node_address}/synchronize"
                            sync_response = requests.get(follower_url)

                            if sync_response.status_code == 200:
                                print(f"Synchronized at {follower_node_address}")
                            else:
                                print(f"Failed to synchronize order at {follower_node_address}")
                except requests.exceptions.RequestException as e:
                    print(f"Error synchronizing order at {follower_node_address}: {e}")


            content_length = int(self.headers["Content-Length"])
            request_body = self.rfile.read(content_length).decode()

            # Parse the request to get the toy name, quantity
            parsed_body = parse_qs(request_body)
            toy_name = parsed_body.get("name", [None])[0]
            quant = float(parsed_body.get("quantity", [0])[0])
            
            #Check for valid quantity
            if quant > 0:

                #Forward request to catalog service to check
                base_url = f"http://{catalog_host}:{catalog_PORT}"
                url = f"{base_url}/orders/{toy_name}/{quant}"
                response = requests.post(url)
                    
                # Send the appropriate response based on the result of the order operation
                if response.status_code == 200:
                    with rwlock.w_locked():
                        order_number += 1
                        current_order_number = order_number
                        update_csv(current_order_number, toy_name, quant)
                        
                        #Order is successful, send it to the replicas as well. 
                        if len(self.server.follower_addresses)>0:
                            order_details = {
                                    "order_number": current_order_number,
                                    "name": toy_name,
                                    "quantity": quant
                                    }
                            
                            #Propagate 
                            for follower_node_address in self.server.follower_addresses:
                                    try:
                                        if follower_node_address != current_server_address:
                                            replica_url = f"{follower_node_address}/replicate_order"
                                            replica_response = requests.post(replica_url, json=order_details)

                                            if replica_response.status_code == 200:
                                                print(f"Order replicated to replica at {follower_node_address}")
                                            else:
                                                print(f"Failed to replicate order to replica at {follower_node_address}")

                                    except requests.exceptions.RequestException as e:
                                        print(f"Error replicating order to replica at {follower_node_address}: {e}")

                        self.send_response(200)    
                        self.send_header("Content-type", "application/json")
                        self.end_headers()
                        response_data = {"data": {"order_number": current_order_number}}
                        response_json = json.dumps(response_data)
                        self.wfile.write(response_json.encode())
                else:
                    self.send_response(400)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()

            # Invalid quantity i.e quantity <= 0    
            else:
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers() 

        
        # Inform replicas about leader
        elif self.path.startswith("/inform_replica"):

            # Get the length of the request data
            content_length = int(self.headers['Content-Length'])
            request_body = self.rfile.read(content_length).decode()

            parsed_body = parse_qs(request_body)
            leader_id = parsed_body.get("leader_id", [None])[0]

            leader_host = os.getenv(f"ORDER_HOST_{leader_id}")
            leader_port = os.getenv(f"ORDER_PORT_{leader_id}")
            leader_address = f"http://{leader_host}:{leader_port}"

            print(f'Order ID {leader_id} is the leader now.')
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({'message': f'From replica: Leader ID {leader_id} is now leader.'}).encode('utf-8'))

        # Select the leader
        elif self.path.startswith("/leaderselection"):

            # Get the length of the request data
            content_length = int(self.headers['Content-Length'])
            request_body = self.rfile.read(content_length).decode()
            parsed_body = parse_qs(request_body)
            
            #Getting leader address 
            leader_id = parsed_body.get("leader_id", [None])[0]

            message = parsed_body.get("message", [0])[0]
            print(message)
            if message == "You win":
                print('I am the leader now.')
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({'message': f'From Leader: Leader ID {leader_id} selected.'}).encode('utf-8'))

         
        elif self.path.startswith("/replicate_order"):

            content_length = int(self.headers['Content-Length'])
            request_body = self.rfile.read(content_length).decode()
            parsed_body = json.loads(request_body)
            order_number = parsed_body.get("order_number")
            name = parsed_body.get("name")
            quantity = parsed_body.get("quantity")
            # print("order_number", order_number, "toy_name", name, "quant", quantity)
            #To update in the replicas 
            
            update_csv(order_number, name, quantity)
            self.send_response(200)    
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Order replicated successfully"}).encode('utf-8'))

        else:
            raise RuntimeError(f'Invalid URL: {self.path}') 

    # Handle GET requests from the frontend 
    def do_GET(self):

        # If the request is for order lookup
        if self.path.startswith("/orders"):

            # Parse the toy name from the request URL
            order_no = self.path.split("/")[-1]

            # Order number lookup
            res = order_lookup(order_no)

            # If the Order number is found, return its data as a JSON response
            if res == 1:
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                response = {
                    "data": {
                        "Order number": order_no,
                        "Toy name": order[int(order_no)]["Toy Name"],
                        "Quantity": order[int(order_no)]["Quantity"]
                    }
                }
                self.wfile.write(json.dumps(response).encode())
            
            # If the Order number is not found, return an error response
            else:
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()

        #To check replica is responsive or not
        elif self.path.startswith("/ping"):
            print("Health check and normal")
            query_params = parse_qs(urlparse(self.path).query)
            if 'message' in query_params and query_params['message'][0] == 'Ping':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"message": "Order service is responsive"}')
        
        # Synchronize replicas
        elif self.path.startswith("/synchronize"):
            with self.server.rwlock.w_locked():
                for follower_address in self.server.follower_addresses:
                    if current_server_address != follower_address:
                        print("Not equal, checking sync")

                        # print("synchronize_replica")
                        last_order_url = f"{follower_address}/get_last_order_number"
                        
                        try:
                            response = requests.get(last_order_url)
                            if response.status_code == 200:
                            # If successful, update replica's database with missed orders
                                replica_order_number = response.json()
                            order_number = get_latest_order_number()  
                            
                            if(order_number != replica_order_number):
                                print("Sync-ing",current_server_address,order_number, replica_order_number)
                                synchronize_replica(order_number, follower_address)
                        except Exception as e:
                            print(f"Error occurred in sync: {e}")
                    else:
                        print(f"Replica at {follower_address} is not available. Skipping synchronization.")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({'message': f'Replicas synchronized '}).encode('utf-8'))

        # To get the order missed for synchronization
        elif self.path.startswith("/get_missed_orders"):
            replica_last_order_number = int(self.path.split("/")[-1])
            missed_orders = get_missed_orders_from_updated_replica(replica_last_order_number)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(missed_orders).encode())

        # Fetch last order number for all replicas
        elif self.path.startswith("/get_last_order_number"):
            last_order_number = get_latest_order_number()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(last_order_number).encode())

        else:
            raise RuntimeError(f'Invalid URL: {self.path}') 
        
# Define a subclass of HTTPServer that uses threading to handle multiple requests concurrently
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    # Override the init function to save metadata in the server
    def __init__(self, host_port_tuple, streamhandler):

        super().__init__(host_port_tuple, streamhandler)
        self.rwlock = RWLock()
        self.protocol_version = "HTTP/1.1"

        #Initialize in memory DB
        init_order(csv_file, order)
        self.follower_addresses = []
        for follower_id in range(1,4):  # Assuming 3 follower nodes
            follower_order_host = os.getenv(f"ORDER_HOST_{follower_id}")
            follower_order_port = os.getenv(f"ORDER_PORT_{follower_id}")
            follower_node_address = f"http://{follower_order_host}:{follower_order_port}"
            self.follower_addresses.append(follower_node_address)
        print("follower_addresses",self.follower_addresses)



def main(port, csv_file):
    # Create a threaded HTTP server that listens on the specified port and handles requests with the OrderRequestHandler class
    httpd = ThreadedHTTPServer(("", port), OrderRequestHandler)
    httpd.executer = ThreadPoolExecutor(
        max_workers=multiprocessing.cpu_count()
    )  
    
    #Read last generated order no. from CSV for data to be persistent
    global order_number
    order_number = get_latest_order_number()
    print("order_number, current_server_address: ",order_number, current_server_address)
    print(f"Serving on port {port}")
    httpd.serve_forever()


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, help='Port number')
    parser.add_argument('--host', type=str, help='Host address')
    parser.add_argument('--unique_id', type=str, help='Unique Id')
    args = parser.parse_args()

    if not args.port or not args.host or not args.unique_id:
        print("Please specify the port number using --port, host address using --host and unique id using --unique_id")
        exit(1)

    order_PORT = args.port
    order_host = args.host
    csv_file = f"order{args.unique_id}.csv"
    print("CSV File name", csv_file)

    current_server_address = f"http://{order_host}:{order_PORT}"
    order = {}
   
    catalog_host = os.getenv("catalog_host")
    catalog_PORT = os.getenv("catalog_PORT")
    print("Catalog Host:", catalog_host, "Catalog Port", catalog_PORT, "order_PORT: ",order_PORT)
    main(int(order_PORT), csv_file)