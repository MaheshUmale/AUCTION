# questdb_config.py
# Purpose: Configuration for connection and migration settings [cite: 16]

CONFIG = {
    "mongodb": {
        "uri": "mongodb://localhost:27017",
        "database": "upstox_strategy_db",
        "collection": "tick_data"
    },
    "questdb": {
        "host": "localhost",
        "port": 9000,          # Web Console/REST
        "ilp_port": 9009,      # Influx Line Protocol port
    },
    "migration": {
        "batch_size": 10000,   # Default batch size [cite: 16]
        "parallel_threads": 4, # Parallel processing support [cite: 16]
        "log_level": "INFO"
    }
}