# Introduction
This application is made as a course project of the course CS315: Principles of Database Systems, Winter 2025, under the guidance of Prof. Arnab Bhattacharya.

OptiQuery is a simple SQL query processing and optimizing tool. It takes input an SQL query and builds the relational algebra tree corresponding to it. After doing so, certain query optimization techniques like predicate pushdown and join optimization can be performed on it. The difference in estimated cost to run the query can be seen in the user interface.

# Setup Instructions
1. Setup PostgreSQL on your machine and create a database for running the application.
2. Download the TPC-H dataset from the instructions given [here](https://github.com/electrum/tpch-dbgen)
3. Run all the commands given in `init-tpch.txt` in the database environment sequentially.
4. Setup python virtualenv:
```
python3 -m venv optiquery
pip install -r requirements.txt
```
5. Modify the database information as per your local setup in `app.py`

# Running
Run the following command to start the application.
```
source optiquery/bin/activate
python3 app.py
```
