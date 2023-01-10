# coding:utf-8
"""
The implementation of UTXO.
The UTXO set, that is, the set of unspent transaction outputs.
Since transactions are stored in blocks, it iterates over each
    block in the blockchain to check each transaction.
However, the entire database requires more than 140 Gb of disk space,
    which means that a person must run a full node if they want to
    verify a transaction.
Moreover, verifying the transaction will require iteration over many blocks.
Therefore, UTXO provides only indexes that do not cost output.
This is a cache built from all blockchain transactions (iterating over blocks,
    but only once) and then used to calculate balances and validate new transactions
Through September 2017, the UTXO set is about 2.7 Gb.
"""

from db import DB, Singleton
from transactions import TXOutput
from couchdb import ResourceNotFound, ResourceConflict
from conf import db_url

class FullTXOutput(object):
    def __init__(self, txid, txoutput, index):
        self.txid = txid
        self.txoutput = txoutput
        self.index = index

"""Data structure of UTXO and database settlement"""
class UTXOSet(Singleton):
    # To distinguish the normal block and UTXO block
    FLAG = 'UTXO'
    def __init__(self, db_url=db_url):
        if not hasattr(self, 'db'):
            self.db = DB(db_url)

    # Remove the spent output,
    # and add the unspent output from the newly mined transaction.
    def update(self, block):
        for tx in block.transactions:
            txid = tx.txid
            key = self.FLAG + txid

            for vout_index, vout in enumerate(tx.vouts):
                vout_dict = vout.serialize()
                vout_dict.update({"index": vout_index})
                tmp_key = key + "-" +str(vout_index)
                try: # generate a new UTXO to the database
                    self.db.create(tmp_key, vout_dict)
                except ResourceConflict as e:
                    print(e)

            for vin in tx.vins:
                vin_txid = vin.txid
                key = self.FLAG + vin_txid + "-" +str(vin.vout)
                doc = self.db.get(key)
                if not doc:
                    continue
                try: # Delete the used UTXO
                    self.db.delete(doc)
                except ResourceNotFound as e:
                    print(e)
        self.set_last_height(block.block_header.height)

    # For safety concern
    def roll_back(self, block):
        for tx in block.transactions:
            txid = tx.txid
            key = self.FLAG + txid
            # Delete the UTXO
            for vout_index, vout in enumerate(tx.vouts):
                tmp_key = key + "-" +str(vout_index)
                doc = self.db.get(tmp_key)
                if not doc:
                    continue
                try:
                    self.db.delete(doc)
                except ResourceNotFound as e:
                    print(e)
            # database in coachDB implementation
            for vin in tx.vins:
                vin_txid = vin.txid
                vout_index = vin.vout
                key = self.FLAG + vin_txid + "-" +str(vin.vout)
                query = {
                    "selector": {
                        "transactions": {
                            "$elemMatch": {
                                "txid": vin_txid
                            }
                        }
                    }
                }
                docs = self.db.find(query)
                if not docs:
                    doc = docs[0]
                else:
                    continue
                transactions = doc.get("transactions", [])
                for tx in transactions:
                    if tx.get("txid", "") == txid:
                        vouts = tx.get("vouts", [])
                        if len(vouts) <= vout_index:
                            continue
                        vout = vouts[vout_index]
                        vout_dict = vout.serialize()
                        vout_dict.update({"index": vout_index})
                        tmp_key = key + "-" +str(vout_index)
                        try:
                            self.db.create(tmp_key, vout_dict)
                        except ResourceConflict as e:
                            print(e)
        self.set_last_height(block.block_header.height-1)

    # Check the transactions, return the unused utxo
    def clear_transactions(self, transactions):
        used_uxto = []
        txs = []
        for tx in transactions:
            txid = tx.txid
            for vin in tx.vins:
                vin_txid = vin.txid
                uxto = (vin_txid, vin.vout)
                if uxto not in used_uxto:
                    used_uxto.append(uxto)
                    txs.append(tx)
        return txs

    # location of the last block
    def get_last_height(self):
        key = self.FLAG + "l"
        if key in self.db:
            return self.db[key]["height"]
        return 0

    # Settlement of the last block for index convenience
    def set_last_height(self, last_height):
        key = self.FLAG + "l"
        if key not in self.db:
            last_height_dict = {"height": last_height}
            self.db[key] = last_height_dict
        else:
            last_doc = self.db.get(key)
            last_doc.update(height=last_height)
            self.db.update([last_doc])

    # Find the unspent output and store it in the database.
    # This is where the cache is.
    def reindex(self, bc):
        key = self.FLAG + "l"
        last_block = bc.get_last_block()

        # Check if it has been created to UTXO or not
        # If no, build the UTXO set from scratch
        if key not in self.db:
            utxos = bc.find_UTXO()
            for txid, index_vouts in utxos.items():
                key = self.FLAG + txid
                # outs = []
                for index_vout in index_vouts:
                    vout = index_vout[1]
                    index = index_vout[0]
                    
                    vout_dict = vout.serialize()
                    vout_dict.update({"index": index})
                    tmp_key = key + "-"+str(index)
                    try:
                        self.db.create(tmp_key, vout_dict)
                    except ResourceConflict as e:
                        print(e)
            if not last_block:
                return
            self.set_last_height(last_block.block_header.height)

        # If yes,update the current UTXO block to the latest block.
        else:
            utxo_last_height = self.get_last_height()
            last_block_height = last_block.block_header.height
            for i in range(utxo_last_height, last_block_height):
                block = bc.get_block_by_height(i)
                self.update(block)

    # Find the outputs which satisfy the amount through the address,
    # it is used to send coins.
    def find_spendable_outputs(self, address, amount):
        utxos = self.find_utxo(address)
        accumulated = 0
        spendable_utxos = []
        for ftxo in utxos:
            output = ftxo.txoutput
            accumulated += output.value
            spendable_utxos.append(ftxo)
            if accumulated >= amount:
                break   # Don't stop until satisfying
        return accumulated, spendable_utxos

    # Query of the UTXO sets through the address,
    # it is used to check the balance.
    def find_utxo(self, address):
        query = {
            "selector": {
                "_id": {
                    "$regex": "^UTXO"
                },
                "pub_key_hash": address
            }
        }
        docs = self.db.find(query)
        utxos = []
        for doc in docs:
            index = doc.get("index", None)
            if index is None:
                continue
            doc_id = doc.id
            txid_index_str = doc_id.replace(self.FLAG, "")
            _flag_index = txid_index_str.find("-")
            txid = txid_index_str[:_flag_index]
            ftxo = FullTXOutput(txid, TXOutput.deserialize(doc), index)
            utxos.append(ftxo)
        return utxos

if __name__ == "__main__":
    utxo = UTXOSet()
    from block_chain import BlockChain
    bc = BlockChain()
    last_block = bc.get_last_block()
    utxo.roll_back(last_block)
    bc.roll_back()