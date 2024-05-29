import json
import http.server
import os
from dotenv import load_dotenv
from http.server import HTTPServer
from socketserver import ThreadingMixIn
from contextlib import contextmanager
from threading import Lock
import csv
import requests
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs,urlparse
import argparse
from datetime import datetime
import threading

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


class Raft(object):
    def __init__(self,log_file,follower_addresses):

        self.log_file = log_file
        self.follower_addresses = follower_addresses
        self.current_term = 1  # Initialize the term to 1
        self.failed_follower = []
        self.rwlock = RWLock()
        self.index = 0

    def init_logfile(self):
        if not os.path.isfile(self.log_file):
            with open(self.log_file, mode='w', newline='') as log_file:
                fieldnames = ['Index','Timestamp', 'Term', 'Event Type', 'Details']
                writer = csv.DictWriter(log_file, fieldnames=fieldnames, delimiter='|')
                writer.writeheader()


    def append_log_entry(self, term, event_type, details):
        with self.rwlock.w_locked(): 
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.index = self.fetch_replica_last_log() +1  # Increment the index for each log entry
            with open(self.log_file, mode='a', newline='') as log_file:
                writer = csv.writer(log_file, delimiter='|')
                writer.writerow([self.index, timestamp, term, event_type, details])

    def fetch_replica_last_log(self ):
        if os.path.isfile(self.log_file):
            with open(self.log_file, "r", newline="") as file:
                reader = csv.DictReader(file, delimiter='|')
                for row in reader:
                    index_number = int(row["Index"])
                return index_number 
        return 0 
    
    def fetch_log_entry_by_index(self, target_index):
        log_entry = None
        # with self.rwlock.r_locked():

            # Open the CSV log file in read mode
        with open(self.log_file, mode='r', newline='') as file:
            reader = csv.DictReader(file, delimiter='|')

            # Iterate over each row in the CSV file
            for row in reader:
                print("row=======", row)
                index = int(row["Index"])  # Assuming index is the first column
                print("in fetch",type(index), index, type(target_index), target_index)
                if index == int(target_index):
                    # If the index matches the target index, store the log entry
                    log_entry = {
                        "index": index,
                        "timestamp": row["Timestamp"],
                        "term": row["Term"],
                        "event_type": row["Event Type"],
                        "details": row["Details"]
                    }
                    break  # Stop iterating once the target index is found
        print("log_entry =====",log_entry )
        return log_entry
    
    def follower_addr(self):
        with self.rwlock.w_locked(): 
            self.follower_node_address = []
            for follower_id in range(1,4):  # Assuming 3 follower nodes
                if int(args.unique_id) != follower_id:
                    print("Unique id: ",args.unique_id, "follower_id: ",follower_id)
                    follower_order_host = os.getenv(f"ORDER_HOST_{follower_id}")
                    follower_order_port = os.getenv(f"ORDER_PORT_{follower_id}")
                    follower_address = f"http://{follower_order_host}:{follower_order_port}"
                    self.follower_node_address.append(follower_address)

        return self.follower_node_address
    
    def replicate_logs(self, log_entries : json,follower_addresses: list):
        success_count = 0
        self.follower_addresses = follower_addresses
        
        # logic to send log entries to followers and ensure consistency
        with self.rwlock.w_locked():
            for follower_address in self.follower_addresses:
                try:    
                        # Create the request body as JSON
                        # request_body = json.dumps(log_entries)

                        request_body = {
                            "log_entries": log_entries,
                            "leader_address": leader_address
                        }
                        print("request_body", request_body)
                        # Send log entries to followers using HTTP POST requests
                        response = requests.post(f"{follower_address}/followers-log", data=json.dumps(request_body))
                        if response.status_code == 200:
                            success_count += 1
                            print(f"Log replicated to {follower_address} successfully.")
                        else:
                            print(f"Failed to replicate logs to {follower_address}. Status code: {response.status_code}")
                except requests.RequestException as e:
                        if follower_address not in self.failed_follower:
                            self.failed_follower.append(follower_address)
                        print("Failed follower: ",self.failed_follower)
                        print(f"Error replicating logs to {follower_address}: {e}")

        #If more than half nodes return responses then the leader commits the log and tells the same to followers and followers also commits
        print("success_count: ",success_count)
        if success_count >= 1:
            print("Log replication successful to at least one follower.")
            return "",True
        else:
            print("Log replication failed to all followers.")
            return self.failed_follower,False

    def get_lastterm(self):
        return self.current_term

    def get_index(self):
        return self.index
        
    

    # def handle_leader_crash(self):
    #     # Logic to handle leader crash and initiate leader re-election
    #     self.current_term += 1  # Increment the term when leader changes
    #     # Additional logic for leader re-election
    #     pass



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

def get_last_line_number(file_path):
    rwlock = RWLock()
    with rwlock.r_locked():
        if os.path.isfile(file_path):
            with open(file_path, 'rb') as file:
                sum = 0
                for _ in file:
                    sum += 1
                return sum

#Order Server class for managing orders and serving HTTP requests.
class OrderRequestHandler(http.server.BaseHTTPRequestHandler):

    # Handle POST requests from the order service
    def do_POST(self):

        rwlock = RWLock()
        global order_number, leader_address
        
        """
        First leader send log details to follower nodes and wait for the response from them if they have appended the entry or not. 
        If yes then the leader commits the log and tells the same to followers and followers also commits
        """
        
        # Check the validity of URL
        if self.path.startswith("/orders"):  
        
            print("POST req")

            content_length = int(self.headers["Content-Length"])
            request_body = self.rfile.read(content_length).decode()

            # Parse the request to get the toy name, quantity
            parsed_body = parse_qs(request_body)
            toy_name = parsed_body.get("name", [None])[0]
            quant = float(parsed_body.get("quantity", [0])[0])
            
            #Check for valid quantity
            if quant > 0:
                
                # Log the event 
                term = self.server.raft_instance.get_lastterm()
                index =  self.server.raft_instance.fetch_replica_last_log()
                # Append in follower nodes
                entries = {
                            "term": term, 
                            "event_type": "ORDER REQUESTED", 
                            "details": f"{toy_name},{quant}",
                            "index": index
                          }
                print("entries",entries)
                raft_replica_address = self.server.raft_instance.follower_addr()
                failed_follower,value = self.server.raft_instance.replicate_logs(entries,raft_replica_address)
                print("Appended or not: ",value)

                # If more than half nodes return success response proceed further else client has to be notified that the order failed.
                if value != True:
                    print("NOT TRUE")
                    v = float('inf')
                    # Used to get last line number from replicas to delete. This can be done dynamically in future.
                    for i in range(1,4):
                        res=get_last_line_number(f"log{i}.txt")
                        print("Minimum line number1: ",res)                        
                        res=min(res,v)

                    print("Minimum line number2: ",res)

                    print("raft_replica_address: ",raft_replica_address, len(raft_replica_address))

                    with rwlock.w_locked():
                        for addr in raft_replica_address:
                            if addr not in failed_follower:
                                print("Failed follower addr: ",failed_follower)
                                print("Replica addr to delete extra lines: ",addr)
                                url = f"{addr}/deletelastline"
                                print("Delete url: ",url)
                                request_body = {"line_number" : res}
                                request_body_json = json.dumps(request_body)
                                try:
                                        response = requests.post(url, data=request_body_json)
                                        if response.status_code == 200:
                                            print("Success: Last line deleted")
                                        else:
                                            print(f'An unexpected status code received: {response.status_code}')
                                except requests.RequestException as e:
                                    print(f'An exception occurred while sending the request to {addr}: {e}')
                    
                    self.send_response(503)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                
                elif value == True:

                    # Append in leader node
                    self.server.raft_instance.append_log_entry(term, "ORDER REQUESTED", f"{toy_name},{quant}")

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
                            if len(raft_replica_address)>0:
                                print("Inside post for follower nodes")
                                order_details = {
                                    "order_number": current_order_number,
                                    "name": toy_name,
                                    "quantity": quant
                                    }
                                
                                #Propagate to follower nodes
                                print("raft_replica_address2: ",raft_replica_address)
                                for node in raft_replica_address:
                                    try:
                                        print("NODE: ",node)
                                        replica_url = f"{node}/replicate_data_nodes"
                                        print("replica_url: ",replica_url)
                                        replica_response = requests.post(replica_url, json=order_details)
                                        if replica_response.status_code == 200:
                                                    print(f"Order replicated to replica at {node}")
                                        else:
                                                    print(f"Failed to replicate order to replica at {node}")

                                    except requests.exceptions.RequestException as e:
                                            print(f"Error replicating order to replica at {node}: {e}")

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

                else:
                    self.send_response(400)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()

            # Invalid quantity i.e quantity <= 0    
            else:
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers() 

        # Select the leader
        elif self.path.startswith("/leaderselection"):

            # Get the length of the request data
            content_length = int(self.headers['Content-Length'])
            request_body = self.rfile.read(content_length).decode()
            parsed_body = parse_qs(request_body)
            
            #Getting leader address 
            leader_id = parsed_body.get("leader_id", [None])[0]
            leader_host = os.getenv(f"ORDER_HOST_{leader_id}")
            leader_port = os.getenv(f"ORDER_PORT_{leader_id}")
            leader_address = f"http://{leader_host}:{leader_port}"

            message = parsed_body.get("message", [0])[0]
            print(message)
            if message == "You win":
                print('I am the leader now.')
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({'message': f'From Leader: Leader ID {leader_id} selected.'}).encode('utf-8'))

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

        elif self.path.startswith("/followers-log"):
            print("Follower url: ",self.path)
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            request_body = json.loads(post_data)
            print("request_body: ",request_body)
            
            # Handle the request body as JSON
            try:
                # print("request_body : ",type(request_body))
                # Example: Log the data or perform actions based on the data
                # Parse the request to get the toy name, quantity
                leader_address = request_body['leader_address']
                l_index = request_body['log_entries']['index']
                term = request_body['log_entries']['term']
                event_type = request_body['log_entries']['event_type']
                details = request_body['log_entries']['details']

                curr_index = self.server.raft_instance.fetch_replica_last_log()
                check_index = l_index
                missed_logs = []
                with rwlock.w_locked():
                    while curr_index!=(check_index-1) and check_index>0:
                        #fetch prev log index of leader
                        url = f"{leader_address}/get_last_log_entry"
                      
                        response = requests.get(url, params={'log_index': check_index})
                        
                        if response.status_code==200:
                            entry = response.json()
                            missed_logs.append(entry)
                        check_index-=1
                        if curr_index == check_index-1:
                            break
                                
                missed_logs.reverse()

                for log in missed_logs:
                    index = log['index']
                    term = log['term']
                    event_type = log['event_type']
                    details = log['details']

                    self.server.raft_instance.append_log_entry(term, event_type, details)

                self.server.raft_instance.append_log_entry(term,event_type,details)
                # Send a success response
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                response_data = {"message": "Log received successfully"}
                self.wfile.write(json.dumps(response_data).encode("utf-8"))

            except json.JSONDecodeError:

                # If JSON decoding fails, send a bad request response
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                response_data = {"error": "Invalid JSON format"}
                self.wfile.write(json.dumps(response_data).encode("utf-8"))

        elif self.path.startswith("/deletelastline"):

            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            request_body = json.loads(post_data)
            print("request_body: ",request_body)

            min_line_number = request_body['line_number']
            current_file_lastnumber = get_last_line_number(f"log{args.unique_id}.txt")
            
            print("current_file_lastnumber: ",current_file_lastnumber)
            print("min_line_number: ",min_line_number)
            file_name = f"log{args.unique_id}.txt"

            #Move the file pointer to the position before the last line ending
            with rwlock.w_locked(): 
                if current_file_lastnumber > min_line_number:
                    with open(file_name, 'rb+') as file:
                        # Move the file pointer to the position before the last line ending
                        file.seek(-2, 2)  # Seek to the second-to-last character from the end
                        while file.read(1) != b'\n':  # Move back until a newline character is found
                            file.seek(-2, 1)  # Move back one more character

                        # Truncate the file from the current position to remove the last line
                        file.truncate()

            self.send_response(200)    
            self.send_header("Content-type", "application/json")
            self.end_headers()

        elif self.path.startswith("/replicate_data_nodes"):

            content_length = int(self.headers['Content-Length'])
            request_body = self.rfile.read(content_length).decode()
            parsed_body = json.loads(request_body)
            order_number = parsed_body.get("order_number")
            name = parsed_body.get("name")
            quantity = parsed_body.get("quantity")

            #To update in the replicas 
            update_csv(order_number, name, quantity)
            self.send_response(200)    
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Order replicated successfully"}).encode('utf-8'))
            
        else:
            raise RuntimeError(f'Invalid URL or network error: {self.path}') 

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

        elif self.path.startswith("/get_last_log_entry"):
            print("Sending last log index from leader to unsynchronized replica")
            query_params = parse_qs(urlparse(self.path).query)
            log_index = query_params['log_index'][0]
            log_entry = self.server.raft_instance.fetch_log_entry_by_index(log_index)
            if log_entry:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(log_entry).encode())
            else:
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.end_headers()
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
        self.raft_instance = Raft(log_file, self.follower_addresses)
        self.raft_instance.init_logfile()      
        # self.raft_instance.init_peeraddr()
        #self.raft_instance.append_log_entry(1, "START", "Raft initialized")
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

    log_file = f"log{args.unique_id}.txt"
    print("log_file: ",log_file)
    current_server_address = f"http://{order_host}:{order_PORT}"
    order = {}
   
    catalog_host = os.getenv("catalog_host")
    catalog_PORT = os.getenv("catalog_PORT")
    print("Catalog Host:", catalog_host, "Catalog Port", catalog_PORT, "order_PORT: ",order_PORT)
    main(int(order_PORT), csv_file)