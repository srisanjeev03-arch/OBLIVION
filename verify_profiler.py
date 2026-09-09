import sys
import os
sys.path.append(os.path.join(os.getcwd(), "src"))

from oblivion.core.discovery import StorageProfiler
import tempfile
import os

with tempfile.NamedTemporaryFile(delete=False) as f:
    f.write(b"hello")
    f.close()

    try:
        p = StorageProfiler()
        profile = p.profile(f.name)
        print(profile)
    finally:
        os.remove(f.name)
