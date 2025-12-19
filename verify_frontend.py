import subprocess
import time
from playwright.sync_api import sync_playwright, expect

def verify_dashboard():
    """
    Launches the trading system, navigates to the dashboard, and takes a screenshot.
    """
    print("Starting frontend verification...")
    process = None
    try:
        # Launch the trading system in the background
        process = subprocess.Popen(["python3", "run.py"])
        print(f"Trading system started with PID: {process.pid}")

        # Give the services time to initialize
        time.sleep(10)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Log console messages
            page.on("console", lambda msg: print(f"Browser console: {msg.text()}"))

            print("Navigating to the dashboard...")
            page.goto("http://localhost:8000")

            # Wait for the WebSocket to connect and receive the first message
            with page.expect_event("console") as console_event:
                expect(console_event.value.text()).to_contain("WebSocket connection established.")

            with page.expect_event("console") as console_event:
                expect(console_event.value.text()).to_contain("Received data:")

            # Wait for the chart to render
            chart = page.locator("#chart")
            expect(chart).to_be_visible()

            print("Taking screenshot...")
            page.screenshot(path="/home/jules/verification/dashboard.png")

            browser.close()
            print("Screenshot saved to /home/jules/verification/dashboard.png")

    finally:
        if process:
            process.terminate()
            process.wait()
            print("Trading system shut down.")

if __name__ == "__main__":
    verify_dashboard()
