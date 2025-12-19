import subprocess
import time
import sys

def main():
    """
    Launches and manages the data ingestor, strategy manager, and API server services.
    """
    print("Starting the trading system...")

    # Start the data ingestor service as a module
    ingestor_process = subprocess.Popen([sys.executable, "-m", "scripts.ingestor"])
    print(f"Data ingestor started with PID: {ingestor_process.pid}")

    # Allow a moment for the ingestor to initialize
    time.sleep(2)

    # Start the strategy manager service as a module
    strategy_manager_process = subprocess.Popen([sys.executable, "-m", "scripts.strategy_manager"])
    print(f"Strategy manager started with PID: {strategy_manager_process.pid}")

    # Start the API server as a module
    api_server_process = subprocess.Popen([sys.executable, "-m", "api.server"])
    print(f"API server started with PID: {api_server_process.pid}")

    try:
        # Monitor the processes
        while True:
            if ingestor_process.poll() is not None:
                print("Data ingestor has stopped unexpectedly. Restarting...")
                ingestor_process = subprocess.Popen([sys.executable, "-m", "scripts.ingestor"])

            if strategy_manager_process.poll() is not None:
                print("Strategy manager has stopped unexpectedly. Restarting...")
                strategy_manager_process = subprocess.Popen([sys.executable, "-m", "scripts.strategy_manager"])

            if api_server_process.poll() is not None:
                print("API server has stopped unexpectedly. Restarting...")
                api_server_process = subprocess.Popen([sys.executable, "-m", "api.server"])

            time.sleep(5)

    except KeyboardInterrupt:
        print("Shutting down the trading system.")
        ingestor_process.terminate()
        strategy_manager_process.terminate()
        api_server_process.terminate()
        ingestor_process.wait()
        strategy_manager_process.wait()
        api_server_process.wait()
        print("System shut down.")

if __name__ == "__main__":
    main()
