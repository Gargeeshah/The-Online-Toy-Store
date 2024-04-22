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