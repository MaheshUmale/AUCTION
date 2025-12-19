import subprocess
import time
import sys
import os
import signal

def main():
    """
    Launches and manages the data ingestor, strategy manager, and API server services.
    """
    print("Starting the trading system...")

    processes = []

    # Start the data ingestor service as a module in a new process session
    ingestor_process = subprocess.Popen([sys.executable, "-m", "scripts.ingestor"], preexec_fn=os.setsid)
    processes.append(ingestor_process)
    print(f"Data ingestor started with PID: {ingestor_process.pid}")

    time.sleep(2)

    # Start the strategy manager service as a module in a new process session
    strategy_manager_process = subprocess.Popen([sys.executable, "-m", "scripts.strategy_manager"], preexec_fn=os.setsid)
    processes.append(strategy_manager_process)
    print(f"Strategy manager started with PID: {strategy_manager_process.pid}")

    # Start the API server as a module in a new process session
    api_server_process = subprocess.Popen([sys.executable, "-m", "api.server"], preexec_fn=os.setsid)
    processes.append(api_server_process)
    print(f"API server started with PID: {api_server_process.pid}")

    def shutdown(signum, frame):
        print("Shutting down the trading system.")
        for p in processes:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            for i, p in enumerate(processes):
                if p.poll() is not None:
                    print(f"Process {p.pid} has stopped unexpectedly. Restarting...")
                    # Relaunch the specific service that failed
                    if i == 0:
                        ingestor_process = subprocess.Popen([sys.executable, "-m", "scripts.ingestor"], preexec_fn=os.setsid)
                        processes[i] = ingestor_process
                    elif i == 1:
                        strategy_manager_process = subprocess.Popen([sys.executable, "-m", "scripts.strategy_manager"], preexec_fn=os.setsid)
                        processes[i] = strategy_manager_process
                    elif i == 2:
                        api_server_process = subprocess.Popen([sys.executable, "-m", "api.server"], preexec_fn=os.setsid)
                        processes[i] = api_server_process
            time.sleep(5)

    except KeyboardInterrupt:
        shutdown(None, None)

if __name__ == "__main__":
    main()
