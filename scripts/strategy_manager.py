import multiprocessing
import json
import time
import sys
import os


from trading_core.stage8_engine import LiveAuctionEngine
import config

# --- Strategy Process ---

class StrategyProcess(multiprocessing.Process):
    def __init__(self, strategy_config):
        super().__init__()
        self.strategy_config = strategy_config
        self.daemon = True

    def run(self):
        """The main entry point for a strategy process."""
        print(f"Starting strategy process for {self.strategy_config['name']}...")

        engine = LiveAuctionEngine(self.strategy_config)
        engine.start_consuming(config.ZMQ_PUB_URL)

# --- Strategy Manager ---

def load_strategy_config(filepath="configs/strategies.json"):
    """Loads the strategy configuration from a JSON file."""
    if not os.path.exists(filepath):
        print(f"Error: Strategy config file not found at {filepath}")
        return []
    with open(filepath, 'r') as f:
        return json.load(f)

def main():
    """Launches and manages strategy processes."""
    print("Starting strategy manager...")

    strategies = load_strategy_config()
    if not strategies:
        print("No strategies to run. Exiting.")
        return

    processes = []
    for strategy_config in strategies:
        # Inject the access token from the global config
        strategy_config['access_token'] = config.ACCESS_TOKEN

        process = StrategyProcess(strategy_config)
        processes.append(process)
        process.start()

    print(f"Launched {len(processes)} strategy processes.")

    try:
        while True:
            for process in processes:
                if not process.is_alive():
                    print(f"Process for strategy {process.strategy_config['name']} has died. Restarting...")
                    new_process = StrategyProcess(process.strategy_config)
                    processes.remove(process)
                    processes.append(new_process)
                    new_process.start()
            time.sleep(5)
    except KeyboardInterrupt:
        print("Shutting down strategy manager.")
        for process in processes:
            process.terminate()
            process.join()

if __name__ == "__main__":
    main()
