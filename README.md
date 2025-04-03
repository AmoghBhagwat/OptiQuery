# Setup Instructions
1. Setup PostgreSQL on your machine and create a database for running the application.
2. Download the TPC-H dataset from the instructions given [here](https://github.com/aleaugustoplus/tpch-data)
3. Run all the commands given in `init-tpch.txt` in the database environment sequentially.
4. Setup python virtualenv:
```
python3 -m venv optiquery
pip install -r requirements.txt
```