# How to start the service w/o using Docker

### Change the environment variables in .env if necessary.

1. Open a terminal and run catalog.py to start the catalog service. 
```shell
cd ${LAB2_PATH}/src/Catalog
```
```python
python3 catalog.py 
```

2. Open another terminal to start the order service.
```shell
cd ${LAB2_PATH}/src/Order
```
```python
python3 order.py 
```

3. Open the third terminal to start the frontend service
```shell
cd ${LAB2_PATH}/src/Frontend-Service
```
```python
python3 frontend-service.py 
```

4. After starting the three services, a client can start sending requests via the port that the frontend is listening to.
```shell
cd ${LAB2_PATH}/src/client
```
```python
python3 client.py 
```

# How to start the service using Docker on Local

1. The three dockerfiles and the docker-compose.yml file is available in the /src folder. For building the three microservices individually, go to the src folder
```shell
cd ${LAB2_PATH}/src
```
Build Frontend:
```
 docker build \
    --build-arg frontend_port=<Frontend-Host> \
    --build-arg order_host=<Order-Host> \
    --build-arg order_PORT=<Order_PORT> \
    --build-arg catalog_host=<catalog-Host> \
    --build-arg catalog_PORT=<catalog-Port> \
    -t frontend-service \
    -f Frontend-Dockerfile .
```

Run Frontend:
```
docker run frontend-service
```

Build Catalog:
```
docker build \
    --build-arg catalog_PORT=<Catalog_Port> \
    --build-arg catalog_csv_file=catalog.csv \
    -t catalog-service \
    -f Catalog-Dockerfile \
    .
```

Run Catalog Service:
```
 docker run catalog-service
```

Order:
```
docker build \
    --build-arg order_host=<Order-Host> \
    --build-arg order_PORT=<Order-Port> \
    --build-arg catalog_host=<Catalog-Host> \
    --build-arg catalog_PORT=<Catalog-Port> \
    -t order-service \
    -f Order-Dockerfile .
```

Run Order Service:
```
 docker run order-service
```


2. To build Docker container for services defined in our Docker Compose configuration file, adjust the environment variables in .env file, and the port in docker-compose.yml file, and this command:
```
docker compose build
```

3. To start the containers defined in our Docker Compose configuration file
```
 docker compose up
```

4. After running the container, go to the client file and run the client file 
```shell
cd ${LAB2_PATH}/src/Client
```
```
 python3 client.py 
```

5. Alternatively, use the build.sh command. 
Grant the permission and run the `build.sh` file
```
 chmod +x build.sh
```
```
 ./build.sh
```

6. To stop the services defined in our Docker Compose configuration file and remove the associated containers, networks, and volumes. 
```
 docker compose down
```

# How to start the replication without using Docker on Local

## Check the .env files for any changes 

## In the src folder, use the run-all.sh script to execute all the services 
```
chmod +x run-all.sh
```

```
./run-all.sh
```

# How to start the services for replicas on AWS

### Change the environment variables in .env if necessary.

1.  First we created an `t2.micro` EC2 instance in the `us-east-1` region on AWS 
```shell
$ aws ec2 run-instances --image-id ami-0d73480446600f555 --instance-type t2.micro --key-name vockey > instance.json
```

2.   Checking status of our instance to find the public DNS name
```shell
aws ec2 describe-instances --instance-id ec2-44-223-61-2.compute-1.amazonaws.com
```

3.  Access the instance via ssh
```shell
chmod 400 labuser.pem
#for our frontend service, which uses port=477
aws ec2 authorize-security-group-ingress --group-name default --protocol tcp --port 4773 --cidr 0.0.0.0/0
ssh -i labsuser.pem ubuntu@ec2-44-223-61-2.compute-1.amazonaws.com
```

4. Inside the instance, install the required packages:
```shell
sudo apt-get install software-properties-common
sudo apt-add-repository universe
sudo apt-get update
sudo apt-get install python3-pip
pip3 install requests
pip3 install python-dotenv
pip3 install pandas
```

5. Cloning our repo on the instance
```shell
Git clone https://github.com/umass-cs677-current/spring24-lab3-Gargeeshah-vaishnavi0401.git
cd /spring24-lab3-Gargeeshah-vaishnavi0401/src 
```

6. Running all the five services
```shell
chmod +x run-all.sh
./run-all.sh 
```

7. Run concurrent clients locally
```shell
cd ${LAB3_PATH}/src/test/load_test
```
```shell
chmod +x client5.sh
./client5.sh 
```
