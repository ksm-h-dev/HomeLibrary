import subprocess
import re
from typing import Optional
from app.models import DiscoveredDrive


DRIVE_TYPE_MAP = {2: "removable", 3: "fixed", 4: "network", 5: "cdrom", 6: "ram"}


async def discover_drives() -> list[DiscoveredDrive]:
    drives = []

    try:
        result = subprocess.run(
            [
                "powershell",
                "-Command",
                "Get-WmiObject Win32_LogicalDisk | Select-Object DeviceID, VolumeName, DriveType, FileSystem, Size, FreeSpace | ConvertTo-Json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and result.stdout.strip():
            import json

            data = json.loads(result.stdout)

            if isinstance(data, dict):
                data = [data]

            for disk in data:
                drive_type = DRIVE_TYPE_MAP.get(disk.get("DriveType", 0), "unknown")

                if drive_type in ["fixed", "removable", "network"]:
                    drives.append(
                        DiscoveredDrive(
                            drive_letter=disk.get("DeviceID", "").rstrip(":"),
                            label=disk.get("VolumeName"),
                            type=drive_type,
                            total_size=_safe_int(disk.get("Size")),
                            free_space=_safe_int(disk.get("FreeSpace")),
                        )
                    )

    except Exception as e:
        print(f"Error discovering drives: {e}")

    return drives


def _safe_int(value) -> Optional[int]:
    try:
        return int(value) if value else None
    except (ValueError, TypeError):
        return None


async def check_drive_online(drive_letter: str) -> bool:
    import os

    path = f"{drive_letter}:\\"
    return os.path.exists(path)


async def get_drive_type(drive_letter: str) -> Optional[str]:
    try:
        result = subprocess.run(
            [
                "powershell",
                "-Command",
                f"(Get-WmiObject Win32_LogicalDisk -Filter \"DeviceID='{drive_letter}:'\").DriveType",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout.strip():
            drive_type_num = int(result.stdout.strip())
            return DRIVE_TYPE_MAP.get(drive_type_num, "unknown")

    except Exception as e:
        print(f"Error getting drive type: {e}")

    return None
