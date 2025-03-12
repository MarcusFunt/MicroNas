#!/usr/bin/env python3
import secrets

def generate_csrf_key(length=32):
    """
    Generates a random CSRF key.
    
    :param length: Number of bytes to generate (default 32, producing a 64-character hex string)
    :return: Hexadecimal representation of the random key.
    """
    return secrets.token_hex(length)

if __name__ == '__main__':
    key = generate_csrf_key()
    print("Your new CSRF key:")
    print(key)
