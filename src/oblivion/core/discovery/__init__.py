import ctypes
import os
import pathlib
from typing import Any, Dict, List, Protocol

from .analyzer import TargetAnalyzer

__all__ = ["StorageProfiler", "TargetAnalyzer"]

# Windows constants
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
FILE_ATTRIBUTE_ENCRYPTED = 0x4000

class StorageProfiler:
    """Read-only storage profiling."""

    def profile(self, path: str) -> dict[str, Any]:
        p = pathlib.Path(path)

        profile_data = {
            "volume_name": "UNKNOWN",
            "volume_serial_number": "UNKNOWN",
            "filesystem": "UNKNOWN",
            "capacity_bytes": "UNAVAILABLE",
            "free_bytes": "UNAVAILABLE",
            "encryption_status": "UNKNOWN",
            "reparse_characteristics": [],
            "media_type": "UNKNOWN",
            "size_bytes": 0,
        }
        profile_data["reparse_characteristics"] = []

        if not p.exists():
            profile_data["limitations"] = ["Target path does not exist"]
            return profile_data

        try:
            # Size
            stat = p.stat()
            profile_data["size_bytes"] = stat.st_size

            # 1. Volume Information using Handle
            # Need to get a handle for GetVolumeInformationByHandleW
            # 0x80000000 = GENERIC_READ
            # 0x00000001 | 0x00000002 = FILE_SHARE_READ | FILE_SHARE_WRITE
            # 3 = OPEN_EXISTING
            # 0x00000080 = FILE_ATTRIBUTE_NORMAL

            handle = ctypes.windll.kernel32.CreateFileW(
                str(p.absolute()),
                0x80000000,
                0x00000001 | 0x00000002,
                None,
                3,
                0x00000080,
                None
            )

            if handle != -1:
                vol_name_buf = ctypes.create_unicode_buffer(256)
                fs_name_buf = ctypes.create_unicode_buffer(256)
                serial_number = ctypes.c_ulong()
                max_comp_len = ctypes.c_ulong()
                fs_flags = ctypes.c_ulong()

                success = ctypes.windll.kernel32.GetVolumeInformationByHandleW(
                    handle,
                    vol_name_buf,
                    ctypes.sizeof(vol_name_buf),
                    ctypes.byref(serial_number),
                    ctypes.byref(max_comp_len),
                    ctypes.byref(fs_flags),
                    fs_name_buf,
                    ctypes.sizeof(fs_name_buf)
                )

                if success:
                    profile_data["volume_name"] = vol_name_buf.value
                    profile_data["volume_serial_number"] = hex(serial_number.value)
                    profile_data["filesystem"] = fs_name_buf.value

                ctypes.windll.kernel32.CloseHandle(handle)

            # 2. Disk Space
            root = os.path.splitdrive(str(p.absolute()))[0] + "\\"
            free_bytes = ctypes.c_ulonglong()
            total_bytes = ctypes.c_ulonglong()
            total_free_bytes = ctypes.c_ulonglong()

            if ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                root,
                ctypes.byref(free_bytes),
                ctypes.byref(total_bytes),
                ctypes.byref(total_free_bytes)
            ):
                profile_data["capacity_bytes"] = total_bytes.value
                profile_data["free_bytes"] = free_bytes.value

            # 3. Attributes
            if hasattr(stat, "st_file_attributes"):
                attrs = stat.st_file_attributes
                reparse_list: list[str] = profile_data["reparse_characteristics"]  # type: ignore
                if attrs & FILE_ATTRIBUTE_REPARSE_POINT:
                    reparse_list.append("reparse_point")
                if attrs & FILE_ATTRIBUTE_ENCRYPTED:
                    profile_data["encryption_status"] = "encrypted"
                else:
                    profile_data["encryption_status"] = "not_encrypted"

        except Exception as e:
            profile_data["limitations"] = [f"Storage profile incomplete: {e!s}"]

        return profile_data


class ITargetAnalyzer(Protocol):
    """Interface for discovering and analyzing targets."""
    async def analyze(self, path: str) -> dict[str, Any]:
        """Analyze target without mutation."""
        ...

class IHasher(Protocol):
    """Interface for computing file hashes."""
    async def sha256(self, path: str) -> str:
        """Compute SHA-256 hash of file."""
        ...

class IStorageProfiler(Protocol):
    """Interface for profiling storage media."""
    async def profile(self, path: str) -> dict[str, Any]:
        """Profile storage containing target."""
        ...
