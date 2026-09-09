import hashlib
import os
import tempfile
from pathlib import Path

import pytest

from oblivion.core.hashing import Hasher


def test_hash_empty_file():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = Path(f.name)
    try:
        # SHA-256 of empty string
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert Hasher.hash_file(path) == expected
    finally:
        os.remove(path)

def test_hash_known_data():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"hello world")
        path = Path(f.name)
    try:
        # SHA-256 of "hello world"
        expected = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        assert Hasher.hash_file(path) == expected
    finally:
        os.remove(path)

def test_hash_large_file():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        # Write 2 chunks (128KB) to ensure chunking works
        data = b"A" * 65536 * 2
        f.write(data)
        path = Path(f.name)
    try:
        expected = hashlib.sha256(data).hexdigest()
        assert Hasher.hash_file(path) == expected
    finally:
        os.remove(path)

def test_hash_non_existent_file():
    with pytest.raises(ValueError):
        Hasher.hash_file(Path("non_existent_file.txt"))

def test_hash_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir)
        with pytest.raises(ValueError):
            Hasher.hash_file(path)
