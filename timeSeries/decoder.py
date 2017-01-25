'''
Created on 08/03/2016

@author: Jose Pedro
'''

from Crypto.Cipher import AES
from Crypto.Hash import SHA256

def decode(encryptedValues, key):
    if key==None:
        values = encryptedValues
    else:
        hashKey = SHA256.new()
        hashKey.update(key.encode('utf_8'))
        key = hashKey.digest()
        
        decoder = AES.new(key, AES.MODE_ECB)
        values = []
        for obj in encryptedValues:
            number = ''
            for s0 in decoder.decrypt(obj).decode("utf-8"):
                if s0.isdigit() or s0=='.':
                    number += s0
                else:
                    break
            values.append(float(number))
    
    return values