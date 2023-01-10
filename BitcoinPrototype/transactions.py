# coding:utf-8
"""
The implementation of transaction.
Since Bitcoin uses a UTXO model, rather than an account model, there is no direct concept of "balance",
    which needs to be obtained by traversing the entire transaction history.
For each new transaction, its input refers to the output of the previous transaction (with the exception of coinbase),
    and the reference refers to the cost. By referring to a previous output,
    you include a previous output in the input of another transaction,
    which is the output of the previous transaction.
The output of the transaction is where the currency is actually stored.
"""

import binascii
import ecdsa
from utils import sum256_hex, hash_public_key, address_to_pubkey_hash

# For convenience, set the subsidy to 1000
subsidy = 1000

"""Transaction output structurecontains the destination address and the amount"""
class TXOutput(object):
    def __init__(self, value, pub_key_hash=''):
        self.value = value
        self.pub_key_hash = pub_key_hash

    def lock(self, address):
        hex_pub_key_hash = binascii.hexlify(address_to_pubkey_hash(address))
        self.pub_key_hash = hex_pub_key_hash

    # Used to check the address belonging
    def is_locked_with_key(self, pub_key_hash):
        return self.pub_key_hash == pub_key_hash

    # Serialize to the dictionary for indexing, json
    def serialize(self):
        return self.__dict__

    def __repr__(self):
        return 'TXOutput(value={value}, pub_key_hash={pub_key_hash})'.format(
            value=self.value, pub_key_hash=self.pub_key_hash)

    @classmethod
    def deserialize(cls, data):
        value = data.get('value', 0)
        pub_key_hash = data.get('pub_key_hash', 0)
        return cls(value, pub_key_hash)

"""Transaction input structure contains the transaction ID,
    previous output indexs,and the signature"""
class TXInput(object):
    def __init__(self, txid, vout, pub_key):
        self.txid = txid
        self.vout = vout
        self.signature = ''
        self.pub_key = pub_key

    # check the address(pkhash)
    def use_key(self, pub_key_hash):
        bin_pub_key = binascii.unhexlify(self.pub_key)
        hash = hash_public_key(bin_pub_key)
        return pub_key_hash == hash

    # Serialize to the dictionary for indexing, json
    def serialize(self):
        return self.__dict__

    def __repr__(self):
        return 'TXInput(txid={txid}, vout={vout})'.format(
            txid=self.txid, vout=self.vout)

    @classmethod
    def deserialize(cls, data):
        txid = data.get('txid', '')
        vout = data.get('vout', 0)
        signature = data.get('signature', '')
        pub_key = data.get('pub_key', '')
        tx_input = cls(txid, vout, pub_key)
        tx_input.signature = signature
        return tx_input

"""To construct a transaction txinput||txoutput, 
    and generate a txid with hashing them."""
class Transaction(object):
    def __init__(self, vins, vouts):
        self.txid = ''
        self.vins = vins
        self.vouts = vouts

    # Generation of the transaction id
    def set_id(self):
        data_list = [str(vin.serialize()) for vin in self.vins]
        vouts_list = [str(vout.serialize()) for vout in self.vouts]
        data_list.extend(vouts_list)
        data = ''.join(data_list)
        hash = sum256_hex(data) # Hash(txinput||txoutput) get the txid
        self.txid = hash

    # If the transaction is coinbase transaction(mining reward), it will not have input.
    def is_coinbase(self):
        return len(self.vins) == 1 and len(self.vins[0].txid) == 0 and self.vins[0].vout == -1

    # Serialize to the dictionary for indexing, json
    def serialize(self):
        return {
            'txid': self.txid,
            'vins': [vin.serialize() for vin in self.vins],
            'vouts': [vout.serialize() for vout in self.vouts]
        }

    @classmethod
    def deserialize(cls, data):
        txid = data.get('txid', '')
        vins_data = data.get('vins', [])
        vouts_data = data.get('vouts', [])
        vins = []
        vouts = []
        for vin_data in vins_data:
            vins.append(TXInput.deserialize(vin_data))

        for vout_data in vouts_data:
            vouts.append(TXOutput.deserialize(vout_data))
        tx = cls(vins, vouts)
        tx.txid = txid
        return tx

    @classmethod
    # define the coinbase transaction
    def coinbase_tx(cls, to, data):
        if not data:
            data = "Reward to '%s'" % to
        txin = TXInput('', -1, data) # the output index is -1
        txout = TXOutput(subsidy, to)
        tx = cls([txin], [txout])
        tx.set_id()
        return tx

    def __repr__(self):
        return 'Transaction(txid={txid}, vins={vins}, vouts={vouts})'.format(
            txid=self.txid, vins=self.vins, vouts=self.vouts)

    """
    Trim the transaction to prepare for signing and verification, and we only need to sign:
    1.Stored in the unlocked output of the public key hash. It identifies the "sender" of a transaction.
    2.The public key hash stored in the new locked output. It identifies the "recipient" of a transaction.
    3.New output value.
    So we should delete the public key in transaction input
    """
    def _trimmed_copy(self):
        inputs = []
        outputs = []
        for vin in self.vins:
            inputs.append(TXInput(vin.txid, vin.vout, None))
        for vout in self.vouts:
            outputs.append(TXOutput(vout.value, vout.pub_key_hash))
        tx = Transaction(inputs, outputs)
        tx.txid = self.txid
        return tx

    """SCORE POINT--Digital signature and verify
        Transactions must be signed, because that's the only way in Bitcoin 
        to guarantee that the sender won't spend money that belongs to someone else.
        We use ECDSA to generate a keypair, 
        private key for signing and public key for verification.
    """
    def sign(self, priv_key, prev_txs):
        if self.is_coinbase():
            return
        tx_copy = self._trimmed_copy()

        for in_id, vin in enumerate(tx_copy.vins): # Iterate over each input in the copy
            prev_tx = prev_txs.get(vin.txid, None)
            if not prev_tx:
                raise ValueError('Previous transaction is error')
            # All transactions are set to "empty" except the current one,
            # and the Inputs are signed separately
            tx_copy.vins[in_id].signature = None
            tx_copy.vins[in_id].pub_key = prev_tx.vouts[vin.vout].pub_key_hash
            tx_copy.set_id() # the hash result is the data we want to sign
            tx_copy.vins[in_id].pub_key = None # reset

            # Use the private key to sign for the transaction.
            sk = ecdsa.SigningKey.from_string(
                binascii.a2b_hex(priv_key), curve=ecdsa.SECP256k1)
            sign = sk.sign(tx_copy.txid.encode())
            self.vins[in_id].signature = binascii.hexlify(sign).decode()

    def verify(self, prev_txs):
        if self.is_coinbase():
            return True
        tx_copy = self._trimmed_copy()

        # is similar with the sign procedure
        for in_id, vin in enumerate(self.vins):
            prev_tx = prev_txs.get(vin.txid, None)
            if not prev_tx:
                raise ValueError('Previous transaction is error')
            tx_copy.vins[in_id].signature = None
            tx_copy.vins[in_id].pub_key = prev_tx.vouts[vin.vout].pub_key_hash
            tx_copy.set_id()
            tx_copy.vins[in_id].pub_key = None

            # Unhex the signature for verification
            sign = binascii.unhexlify(self.vins[in_id].signature)
            # use the public key to verify the signature
            vk = ecdsa.VerifyingKey.from_string(
                binascii.a2b_hex(vin.pub_key), curve=ecdsa.SECP256k1)
            if not vk.verify(sign, tx_copy.txid.encode()):
                return False # reject the transaction
        return True