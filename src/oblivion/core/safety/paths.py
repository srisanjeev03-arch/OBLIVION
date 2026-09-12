"""Oblivion path safety - safe canonicalization, allowed-roots, system-volume, reparse detection."""
import ctypes
import os
import sys
from pathlib import Path
from typing import Any, cast


class PathSafetyError(Exception):
    """Raised when a path safety check fails."""


#: Separator for the persisted form of a file identity. The identity itself stays
#: the tuple ``SafePathValidator._get_file_id`` returns; these two functions only
#: move it in and out of a text column, so no second identity model exists.
_FILE_ID_SEPARATOR = ":"


def encode_file_id(file_id: tuple[int, int, int] | None) -> str | None:
    """Render a file identity for storage, or ``None`` when there is none.

    ``None`` in means ``None`` out: a platform that cannot produce a file
    identity must persist an absent one rather than a placeholder, so a reader
    can tell "not observable here" from "observed and recorded".
    """
    if file_id is None:
        return None
    return _FILE_ID_SEPARATOR.join(str(int(part)) for part in file_id)


def decode_file_id(raw: str | None) -> tuple[int, int, int] | None:
    """Read a stored file identity back as the tuple the validator compares.

    Anything that is not exactly three integers returns ``None`` - an
    unparseable identity is an absent one, and callers must fail closed on
    absence rather than treat a malformed value as a match.
    """
    if not raw:
        return None
    parts = raw.split(_FILE_ID_SEPARATOR)
    if len(parts) != 3:
        return None
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


class SafePathValidator:
    """
    Enforces Oblivion path safety rules:
    - Canonicalization and normalization
    - OBLIVION_ALLOWED_ROOTS enforcement (ADR-008)
    - System-drive protection via volume identity (ADR-009)
    - Reparse point / junction / symlink detection (fail-closed)
    - TOCTOU-aware revalidation
    """
    def __init__(self, allowed_roots: list[str] | None = None):
        if allowed_roots:
            self.allowed_roots: list[str] = [os.path.abspath(p) for p in allowed_roots]
        else:
            # Fallback to OBLIVION_ALLOWED_ROOTS env var or a safe temp dir
            env_roots = os.environ.get("OBLIVION_ALLOWED_ROOTS")
            if env_roots:
                self.allowed_roots = [os.path.abspath(p.strip()) for p in env_roots.split(";") if p.strip()]
            else:
                import tempfile
                self.allowed_roots = [os.path.abspath(tempfile.gettempdir())]

        # Capture system volume serial for ADR-009 protection
        self.system_volume_serial: str | None = self._get_system_volume_serial()

    def _get_system_volume_serial(self) -> str | None:
        """Captures the VolumeSerialNumber of the system drive (C:)."""
        if sys.platform != "win32":
            return None
        try:
            kernel32 = ctypes.windll.kernel32
            volume_name_buffer = ctypes.create_unicode_buffer(1024)
            file_system_name_buffer = ctypes.create_unicode_buffer(1024)
            serial_number = ctypes.c_uint32()
            max_component_length = ctypes.c_uint32()
            file_system_flags = ctypes.c_uint32()

            # Using C:\ as the system drive reference
            if kernel32.GetVolumeInformationW(
                "C:\\",
                volume_name_buffer, 1024,
                ctypes.byref(serial_number),
                ctypes.byref(max_component_length),
                ctypes.byref(file_system_flags),
                file_system_name_buffer, 1024
            ):
                return hex(serial_number.value).upper()
        except Exception:
            pass
        return None

    def _get_file_id(self, path: str) -> tuple[int, int, int] | None:
        """Gets a unique identifier (volume serial + file index) for a file on Windows."""
        if sys.platform != "win32":
            return None
        try:
            from ctypes import wintypes

            # Open the file to get a handle
            FILE_SHARE_READ = 0x00000001
            OPEN_EXISTING = 3
            FILE_FLAG_BACKUP_SEMANTICS = 0x02000000

            handle = ctypes.windll.kernel32.CreateFileW(
                path,
                0, # No access
                FILE_SHARE_READ,
                None,
                OPEN_EXISTING,
                FILE_FLAG_BACKUP_SEMANTICS,
                None
            )

            if handle == -1: # INVALID_HANDLE_VALUE
                return None

            class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("dwFileAttributes", wintypes.DWORD),
                    ("ftCreationTime", wintypes.FILETIME),
                    ("ftLastAccessTime", wintypes.FILETIME),
                    ("ftLastWriteTime", wintypes.FILETIME),
                    ("dwVolumeSerialNumber", wintypes.DWORD),
                    ("nFileSizeHigh", wintypes.DWORD),
                    ("nFileSizeLow", wintypes.DWORD),
                    ("nNumberOfLinks", wintypes.DWORD),
                    ("nFileIndexHigh", wintypes.DWORD),
                    ("nFileIndexLow", wintypes.DWORD),
                ]

            info = BY_HANDLE_FILE_INFORMATION()
            success = ctypes.windll.kernel32.GetFileInformationByHandle(handle, ctypes.byref(info))
            ctypes.windll.kernel32.CloseHandle(handle)

            if success:
                return (info.dwVolumeSerialNumber, info.nFileIndexHigh, info.nFileIndexLow)
        except Exception:
            pass
        return None

    def get_volume_serial(self, path: str) -> str | None:
        """Gets the VolumeSerialNumber for the volume containing the given path."""
        if sys.platform != "win32":
            return None
        try:
            kernel32 = ctypes.windll.kernel32
            # Get the root path (e.g., D:\)
            root_path = os.path.splitdrive(os.path.abspath(path))[0] + "\\"

            serial_number = ctypes.c_uint32()
            if kernel32.GetVolumeInformationW(
                root_path,
                None, 0,
                ctypes.byref(serial_number),
                None, None, None, 0
            ):
                return hex(serial_number.value).upper()
        except Exception:
            pass
        return None

    def canonicalize(self, raw_path: str) -> str:
        """Resolves path to absolute, normalized form."""
        if not raw_path or not isinstance(raw_path, str):
            raise PathSafetyError("Path must be a non-empty string")
        # abspath handles normalization and resolution on Windows
        return os.path.abspath(raw_path)

    def is_allowed(self, path: str) -> bool:
        """Verifies path is a descendant of an allowed root (ADR-008)."""
        try:
            resolved = self.canonicalize(path)
            p_resolved = Path(resolved)
        except PathSafetyError:
            return False

        for root in self.allowed_roots:
            try:
                p_root = Path(root)
                # Check if path is root or inside root
                if p_resolved == p_root or p_root in p_resolved.parents:
                    return True
            except (ValueError, RuntimeError):
                continue
        return False

    def reject_reparse(self, path: str) -> bool:
        """Detects reparse points, junctions, and symlinks (fail-closed)."""
        try:
            p = Path(path)
            # is_symlink handles symlinks
            if p.is_symlink():
                return True

            # Windows-specific junction/reparse point check
            if sys.platform == "win32":
                FILE_ATTRIBUTE_REPARSE_POINT = 0x400
                attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
                if attrs != -1 and (attrs & FILE_ATTRIBUTE_REPARSE_POINT):
                    return True
            return False
        except Exception:
            # If we can't determine, fail-closed
            return True

    def is_system_volume(self, path: str) -> bool:
        """
        Protects boot-critical volumes via VolumeSerialNumber (ADR-009).
        Also maintains prefix-based blacklists for secondary protection.
        """
        try:
            resolved = self.canonicalize(path)

            # 1. Volume Serial Protection (ADR-009)
            if self.system_volume_serial:
                target_serial = self.get_volume_serial(resolved)
                if target_serial == self.system_volume_serial:
                    return True

            # 2. Path Prefix Protection (Defense in depth)
            prefixes: list[str] = []
            if sys.platform == "win32":
                win_dir = os.environ.get("SystemRoot", "C:\\Windows")
                prog_files = os.environ.get("ProgramFiles", "C:\\Program Files")
                prog_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
                prefixes.extend([win_dir, prog_files, prog_files_x86])

            for prefix in prefixes:
                if prefix and str(resolved).lower().startswith(prefix.lower()):
                    return True

            return False
        except Exception:
            # Fail-closed
            return True

    def validate_ancestor_reparse(self, canonical_path: str, matched_root: str) -> bool:
        """
        Validates every ancestor directory between matched_root and canonical_path.
        Rejects if any ancestor along the path is a junction, symlink, or reparse point.
        """
        try:
            target_p = Path(canonical_path)
            root_p = Path(matched_root)

            # Start from the direct parent and walk up until the allowed root
            current = target_p.parent if target_p.is_file() or target_p.exists() else target_p
            while current != root_p and root_p in current.parents:
                if self.reject_reparse(str(current)):
                    return False
                current = current.parent

            # Check root itself
            if self.reject_reparse(str(root_p)):
                return False

            return True
        except Exception:
            return False

    def validate_descendants_reparse(self, dir_path: str, root_boundary: str) -> bool:
        """
        For recursive directory operations, inspects all descendants.
        Rejects if any descendant is an unsafe junction/symlink pointing outside scope.
        """
        try:
            p_dir = Path(dir_path)
            p_root = Path(root_boundary)
            if not p_dir.exists() or not p_dir.is_dir():
                return True

            for root, dirs, files in os.walk(str(p_dir), topdown=True, followlinks=False):
                current_root_p = Path(root)

                # Check if current directory itself is a reparse point
                if current_root_p != p_dir and self.reject_reparse(str(current_root_p)):
                    return False

                for d in dirs:
                    d_path = current_root_p / d
                    if self.reject_reparse(str(d_path)):
                        return False
                    # Check that resolved path is inside root boundary
                    try:
                        resolved_d = Path(os.path.abspath(str(d_path)))
                        if resolved_d != p_root and p_root not in resolved_d.parents:
                            return False
                    except Exception:
                        return False

                for f in files:
                    f_path = current_root_p / f
                    if self.reject_reparse(str(f_path)):
                        return False

            return True
        except Exception:
            return False

    def validate_target(self, raw_path: str, is_directory_tree: bool = False, require_existing_identity: bool = True) -> dict[str, Any]:
        """Performs full safety validation for a target path including ancestor and descendant checks."""
        result: dict[str, Any] = {
            "valid": False,
            "path": raw_path,
            "canonical": None,
            "errors": [],
            "warnings": [],
            "volume_serial": None
        }

        errors: list[str] = cast(list[str], result["errors"])
        warnings: list[str] = cast(list[str], result["warnings"])

        try:
            canonical = self.canonicalize(raw_path)
            result["canonical"] = canonical
            result["volume_serial"] = self.get_volume_serial(canonical)
        except PathSafetyError as e:
            errors.append(str(e))
            return result

        # 1. System Volume Protection (ADR-009).  Do this before reporting a
        # scope error so protected targets are never obscured by configuration.
        if self.is_system_volume(canonical):
            errors.append("System-volume or boot-critical path rejected")
            return result

        # 2. Scope Containment (ADR-008)
        matched_root: str | None = None
        p_canonical = Path(canonical)
        for root in self.allowed_roots:
            p_root = Path(root)
            if p_canonical == p_root or p_root in p_canonical.parents:
                matched_root = root
                break

        if not matched_root:
            errors.append(f"Target outside allowed roots: {self.allowed_roots}")
            return result

        # 3. Ancestor Reparse Point Check (Phase 20)
        if not self.validate_ancestor_reparse(canonical, matched_root):
            errors.append("Ancestor reparse point, junction, or symlink detected (fail-closed)")
            return result

        # 4. Leaf Reparse Point Check (Fail-closed)
        if self.reject_reparse(canonical):
            errors.append("Reparse point, junction, or symlink detected (fail-closed)")
            return result

        # 5. Descendants Reparse Check for directory trees
        if is_directory_tree and Path(canonical).is_dir():
            if not self.validate_descendants_reparse(canonical, matched_root):
                errors.append("Unsafe descendant reparse point or junction escaping boundary detected (fail-closed)")
                return result

        # 6. Windows destructive targets require stable volume and file
        # identity.  Absent identity must never fall through to an operation.
        if sys.platform == "win32" and require_existing_identity and (result["volume_serial"] is None or self._get_file_id(canonical) is None):
            errors.append("Target identity could not be established (fail-closed)")
            return result

        result["valid"] = True
        return result


    def revalidate_handle(self, path: str, expected_serial: str, expected_file_id: tuple[int, int, int] | None = None) -> bool:
        """
        TOCTOU-aware revalidation.
        Verifies the volume serial and file index still match immediately before an operation.
        """
        try:
            current_serial = self.get_volume_serial(path)
            if current_serial != expected_serial:
                return False

            if expected_file_id:
                current_file_id = self._get_file_id(path)
                return current_file_id == expected_file_id

            return True
        except Exception:
            return False
