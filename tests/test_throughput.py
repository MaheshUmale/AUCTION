import unittest
import time
import json
from unittest.mock import MagicMock, patch
from trading_core.stage8_engine import LiveAuctionEngine, LiveMarketRouter

class TestThroughput(unittest.TestCase):
    def setUp(self):
        """Set up a mock engine and router for testing."""
        self.mock_engine = MagicMock(spec=LiveAuctionEngine)
        self.router = LiveMarketRouter(self.mock_engine)
        with open('WSS_FEED_SAMPLE_JSON.txt', 'r') as f:
            # Read the first JSON object from the file
            content = f.read().split('+++++++++++++++++++++')[0]
            self.sample_feed = json.loads(content)

    def tearDown(self):
        """Clean up resources after tests."""
        self.router.shutdown()

    def test_throughput_with_threading(self):
        """Test the throughput of the asynchronous on_message handler."""
        start_time = time.time()
        num_messages = 1000
        # Get the first instrument key from the sample feed
        instrument_key = next(iter(self.sample_feed['feeds']))
        for i in range(num_messages):
            # Assign a unique identifier to each message to track it
            self.sample_feed['feeds'][instrument_key]['fullFeed']['marketFF']['ltpc']['ltt'] = str(time.time())
            self.router.on_message(self.sample_feed)

        # Wait for all futures to complete by shutting down the executor
        self.router.executor.shutdown(wait=True)

        end_time = time.time()
        duration = end_time - start_time
        messages_per_second = num_messages / duration

        print(f"\n[Threaded] Processed {num_messages} messages in {duration:.2f} seconds ({messages_per_second:.2f} msg/s)")

    def test_throughput_without_threading(self):
        """Test the throughput of the synchronous _save_feed_data method."""
        # This test is intended to run synchronously for comparison
        start_time = time.time()
        num_messages = 1000

        for i in range(num_messages):
            for symbol, feed in self.sample_feed.get("feeds", {}).items():
                # Correctly call the method and unpack the returned tuple
                result = self.router._save_feed_data(symbol, feed)
                self.assertIsInstance(result, tuple, "The return value should be a tuple.")
                self.assertEqual(len(result), 2, "The tuple should contain two elements.")

                parsed_tick, parsed_candles = result

                # Further assertions can be added here if needed
                # For example, check if parsed_tick is a dict or None
                self.assertTrue(isinstance(parsed_tick, dict) or parsed_tick is None)
                self.assertIsInstance(parsed_candles, list)

        end_time = time.time()
        duration = end_time - start_time
        messages_per_second = num_messages / duration

        print(f"\n[Synchronous] Processed {num_messages} messages in {duration:.2f} seconds ({messages_per_second:.2f} msg/s)")

if __name__ == '__main__':
    unittest.main()