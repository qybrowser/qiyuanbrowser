"""AES-256-CBC encryption for the fingerprint payload.

Byte-for-byte compatible with the cloud backend (``backend/app/utils/crypto.py``)
so the qiyuan client browser can decrypt what this SDK serves:

    base64( IV[16] + AES-256-CBC( PKCS7(json_utf8) ) )

The key is the fixed string ``+Agxf52VeOuzcW4E8DjpngpcaCzsG+tnfKGBvLpO6ko=`` right-padded with
NUL bytes to 32 bytes.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any, Optional

from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Signature import pkcs1_15
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad

# Chromium uses the current backend key. The bundled Firefox 153.0.4 xul.dll
# still embeds the legacy key; its v2 token-derived key must use that value.
AES_SECRET_KEY = "+Agxf52VeOuzcW4E8DjpngpcaCzsG+tnfKGBvLpO6ko="
FIREFOX_AES_SECRET_KEY = "aes-key-32-bytes-change!!!!!"

_KEYS_DIR = os.path.join(os.path.dirname(__file__), "keys")


def derive_aes_key_v2(token: str, secret: str = AES_SECRET_KEY) -> bytes:
    """version 2.0 AES key: sha256(固定key + '_qiyuan_' + 用户认证token) -> 32 bytes."""
    material = secret + "_qiyuan_" + (token or "")
    return hashlib.sha256(material.encode("utf-8")).digest()


def _key() -> bytes:
    k = AES_SECRET_KEY.encode("utf-8")
    if len(k) < 32:
        k = k.ljust(32, b"\0")
    return k[:32]


def encrypt(data: str, key: Optional[bytes] = None) -> str:
    iv = get_random_bytes(AES.block_size)
    cipher = AES.new(key or _key(), AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(pad(data.encode("utf-8"), AES.block_size))
    return base64.b64encode(iv + ciphertext).decode("utf-8")


def encrypt_json(data: Any, key: Optional[bytes] = None) -> str:
    return encrypt(json.dumps(data, ensure_ascii=False), key)


def decrypt(encrypted_data: str, key: Optional[bytes] = None) -> str:
    raw = base64.b64decode(encrypted_data)
    iv, ciphertext = raw[: AES.block_size], raw[AES.block_size:]
    cipher = AES.new(key or _key(), AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(ciphertext), AES.block_size).decode("utf-8")


def decrypt_json(encrypted_data: str, key: Optional[bytes] = None) -> Any:
    return json.loads(decrypt(encrypted_data, key))


# --- AES encrypt + RSA sign (encrypt-then-sign) ------------------------------
# 密文 = base64( SIGN[keysize/8] + IV[16] + AES-256-CBC(PKCS7(json)) )
#   - AES 密钥由 token 派生（derive_aes_key_v2），两端各自算出、不传输；
#   - SIGN = RSASSA-PKCS1-v1_5(私钥, SHA-256(IV+密文))，服务端持私钥签名；
#   - 内核只需内置公钥验签 + 用 token 派生 AES 密钥解密，私钥永不下发。

def _load_public_key() -> RSA.RsaKey:
    pem = os.environ.get("CHROMIUM_SDK_RSA_PUBLIC_KEY")
    if pem:
        return RSA.import_key(pem)
    with open(os.path.join(_KEYS_DIR, "rsa_public.pem"), "rb") as fh:
        return RSA.import_key(fh.read())


def _load_private_key() -> RSA.RsaKey:
    pem = os.environ.get("CHROMIUM_SDK_RSA_PRIVATE_KEY")
    if pem:
        return RSA.import_key(pem)
    with open(os.path.join(_KEYS_DIR, "rsa_private.pem"), "rb") as fh:
        return RSA.import_key(fh.read())


def sign_encrypt(data: str, key: bytes) -> str:
    """AES(key) 加密后用私钥对密文签名，返回 base64(SIGN + IV + 密文)。"""
    iv = get_random_bytes(AES.block_size)
    ciphertext = AES.new(key, AES.MODE_CBC, iv).encrypt(
        pad(data.encode("utf-8"), AES.block_size)
    )
    blob = iv + ciphertext
    signature = pkcs1_15.new(_load_private_key()).sign(SHA256.new(blob))
    return base64.b64encode(signature + blob).decode("utf-8")


def sign_encrypt_json(data: Any, key: bytes) -> str:
    return sign_encrypt(json.dumps(data, ensure_ascii=False), key)


def verify_decrypt(encrypted_data: str, key: bytes) -> str:
    """公钥验签 + AES(key) 解密（与内核侧逻辑一致，供自测）。"""
    raw = base64.b64decode(encrypted_data)
    ks = _load_public_key().size_in_bytes()  # 2048-bit -> 256
    signature, blob = raw[:ks], raw[ks:]
    pkcs1_15.new(_load_public_key()).verify(SHA256.new(blob), signature)
    iv, ciphertext = blob[: AES.block_size], blob[AES.block_size:]
    return unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(ciphertext), AES.block_size).decode("utf-8")


def verify_decrypt_json(encrypted_data: str, key: bytes) -> Any:
    return json.loads(verify_decrypt(encrypted_data, key))
