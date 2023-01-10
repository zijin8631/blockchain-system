# coding:utf-8
from utils import Singleton

class TxPool(Singleton):
    SIZE = 2
    def __init__(self):
        if not hasattr(self, "txs"):
            self.txs = []

    # To check if the pool is full, if so, return True, else return False
    def is_full(self):
        return len(self.txs) >= self.SIZE

    # tx:the transaction
    #add transaction in the pool
    def add(self, tx):
        self.txs.append(tx)
    # clear all data
    def clear(self):
        self.txs.clear()
