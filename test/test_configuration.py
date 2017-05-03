import unittest
import processTimeTrackingEntries
import os


class ConfigurationTest(unittest.TestCase):

    configuration = {}

    def setUp(self):
        self.configuration = processTimeTrackingEntries.read_configuration(
            os.path.join(os.path.abspath(os.path.dirname(__file__)), 'config_test.ini'))

    def test_missing_option(self):
        global configuration
        self.assertRaises(KeyError, lambda: self.configuration['gibtesnicht'])


def main():
    unittest.main()

if __name__ == '__main__':
    main()