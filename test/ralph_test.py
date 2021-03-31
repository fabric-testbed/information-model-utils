import unittest

from fimutil.ralph.ralph_uri import RalphURI
from fimutil.ralph.worker_node import WorkerNode


class RalphTest(unittest.TestCase):

    def testRalphComponents(self):
        self.ru = RalphURI(token="token", base_uri="https://something")
        self.wn = WorkerNode(uri="https://something", ralph=self.ru)
