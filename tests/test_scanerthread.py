import unittest
from abhard.scaner_thread import ScanerThread


class ScanerThreadTestCase(unittest.TestCase):
    def setUp(self):
        self.thread = ScanerThread(3, '/dev/null')  # Mock device

    def tearDown(self):
        self.thread.running = False
        return super().tearDown()


if __name__ == '__main__':
    unittest.main()
