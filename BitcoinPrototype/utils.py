# coding:utf-8
"""
A toolkit package, contains hash, from public key to keyhash(ripemd160),
from address to public key hash.
"""
import hashlib
import binascii
import base58
import threading

# define utf-8 encode/decode form
def encode(str, code='utf-8'):
    return str.encode(code)

def decode(bytes, code='utf-8'):
    return bytes.decode(code)

def sum256_hex(*args):
    m = hashlib.sha256()
    for arg in args:
        if isinstance(arg, str):
            m.update(arg.encode())
        else:
            m.update(arg)
    return m.hexdigest()

def sum256_byte(*args):
    m = hashlib.sha256()
    for arg in args:
        if isinstance(arg, str):
            m.update(arg.encode())
        else:
            m.update(arg)
    return m.digest()

"""From key to key hash, combining version, checksum and then 
base58 encode can get a standard address"""
def hash_public_key(pubkey):
    ripemd160 = hashlib.new('ripemd160')
    ripemd160.update(hashlib.sha256(pubkey).digest())
    return ripemd160.digest()

"""From address decode and get the keyhash"""
def address_to_pubkey_hash(address):
    return base58.b58decode_check(address)[1:]

class Singleton(object):
    _instance_lock = threading.Lock()
    __instance = None

    def __new__(cls, *args, **kwargs):
        
        if cls.__instance is None:
            with Singleton._instance_lock:
                cls.__instance = super(
                    Singleton, cls).__new__(cls)
        return cls.__instance