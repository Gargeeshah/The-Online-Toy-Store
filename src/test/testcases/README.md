**Unit test cases for catalog service test**

1. Test the following endpoints for the catalog service.

```shell
cd ${LAB2_PATH}/src/test/testcases
```
```python
python3 catalog_test.py 
```
a. When Toy is present in catalog

http://localhost:8832/product/Tux

http://localhost:8832/product/Fox

http://localhost:8832/product/Python

http://localhost:8832/product/Whale

http://localhost:8832/product/Elephant

http://localhost:8832/product/Dolphin

b. When Toy is not present in catalog

http://localhost:8832/product/Monkey

http://localhost:8832/product/Rabbit

http://localhost:8832/product/Cheetah

c. Invalid Toy name 

http://localhost:8832/product/

2. Test the following endpoints for the order service.

```shell
cd ${LAB2_PATH}/src/test/testcases
```
```python
python3 order_test.py 
```
a. Invalid quantity

http://localhost:2231/orders/Rabbit/-20

http://localhost:2231/orders/Dolphin/-2

http://localhost:2231/orders/Whale/0

http://localhost:2231/orders/Elephant/22.3

b. Toy exists and valid quantity

http://localhost:2231/orders/Fox/100

http://localhost:2231/orders/Python/50

c. Toy exists but buy quantity exceeds the stock

http://localhost:2231/orders/Tux/1000

http://localhost:2231/orders/Monkey/22

e. Toy not found

http://localhost:2231/orders/Book/12


3. Test the following endpoints for the application service.

```shell
cd ${LAB2_PATH}/src/test/testcases
```
```python
python3 application_test.py 
```
a. Toy name exists but invalid quantity

GET URL: http://localhost:8007/product/Rabbit

POST URL: http://localhost:8007/product/Rabbit/-20

GET URL: http://localhost:8008/product/Whale

POST URL: http://localhost:8008/product/Whale/0

GET URL: http://localhost:8008/product/Dolphin

POST URL: http://localhost:8008/product/Dolphin/-2

b. Toy name exists but quantity exceeds the stock

GET URL: http://localhost:8008/product/Fox

POST URL:  http://localhost:8008/product/Fox/100

c. Toy exists and valid quantity

GET URL: http://localhost:8008/product/Python

POST URL: http://localhost:8008/product/Python/50

d. Toy not found

GET URL: http://localhost:8008/product/Monkey

POST URL: http://localhost:8008/product/Monkey/22

