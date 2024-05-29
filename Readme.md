# Asterix and Double Trouble

### Goals

The Gauls have really taken to online commerce and buying toys online has become their village pass time. To ensure high performance and tolerance to failures, they have decided to adopt modern disstributed systems design practices.

The Toy Store application consists of three microservices: a front-end service, a catalog service, and an order service.

The front-end service exposes the following REST APIs:

GET /product/<toy_name>
POST /orders/<quantity>
In addition, the front-end service will provide a new REST API that allows clients to query existing orders:

GET /orders/<order_number>

This API returns a JSON reply with a top-level data object with the three fields: number, name, and quantity. If the order number doesn't exist, a JSON reply with a top-level error object should be returned. The error object should contain two fields: code and message

The interfaces used between the microservices. Each microservice handle requests concurrently.

Added some variety to the toy offering by initializing your catalog with at least 10 different toys. Each toy should have an initial volume of 100.

The client first queries the front-end service with a random stock, then it will make a follow-up order request with probability p (make p an adjustable variable). I decide whether the toy query request and an order request use the same connection. The client will repeat the aforementioned steps for a number of iterations, and record the order number and order information if an order request was successful. Before exiting, the client will retrieve the order information of each order that was made using the order query request, and check whether the server reply matches the locally stored order information.

Please refer Design docs for more insights on implementation detail.