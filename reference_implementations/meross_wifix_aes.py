
from hashlib import md5
from base64 import b64decode
from base64 import b64encode

from Crypto.Cipher import AES

class AESCipher:
    def __init__(self, key):
        # Meross uses an md5 hex string for key
        self.key = md5(key.encode('utf-8')).hexdigest().encode('utf-8')

    def encrypt(self, data):
        # Iv is always 16 * the ascii character 0, not to be confused with null (0x0)
        iv = b'0' * AES.block_size
        self.cipher = AES.new(self.key, AES.MODE_CBC, iv)

        # For some reason meross has unconventional padding of null (0x0), so we cannot rely on builtins
        padding = (AES.block_size - (len(data) % AES.block_size)) + len(data)
        return [b64encode(iv), b64encode(self.cipher.encrypt(data.ljust(padding, '\0').encode('utf-8')))]

    def decrypt(self, iv, data):
        iv = b64decode(iv)
        data = b64decode(data)
        self.cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return self.cipher.decrypt(data).rstrip(b'\0')


if __name__ == '__main__':
    # Dummy password to encrypt / decrypt
    password = "you found a secret"

    # Values are bespoke to each device and obtained from a GET to Appliance.System.Hardware, e.g:
    # {
    #     "header": {...},
    #     "payload": {
    #         "hardware": {
    #         "type": "mss710",
    #         "subType": "un",
    #         "version": "8.0.0",
    #         "chipType": "rtl8720cf",
    #         "uuid": "2308283569760958070148e1e9d7c243",
    #         "macAddress": "48:e1:e9:d7:c2:43"
    #         }
    #     }
    # }
    type_value = "mss710"
    uuid_value = "2308283569760958070148e1e9d7c243"
    mac_address_value = "48:e1:e9:d7:c2:43"

    # Key for the AES cipher is derived from a concatenation of the 3 values
    key = type_value + uuid_value + mac_address_value

    iv, data =  AESCipher(key).encrypt(password)
    print ('Encrypt:', data.decode())
    print('Decrypt:', AESCipher(key).decrypt(iv, data).decode())

