import os
import subprocess
from typing import Optional
from app.models import DiscoveredDrive, CatalogInfo


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


async def get_volume_label(drive_letter: str) -> Optional[str]:
    try:
        result = subprocess.run(
            [
                "powershell",
                "-Command",
                f"(Get-Volume -DriveLetter {drive_letter} -ErrorAction SilentlyContinue).FileSystemLabel",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()

    except Exception as e:
        print(f"Error getting volume label: {e}")

    return None


def _safe_int(value) -> Optional[int]:
    try:
        return int(value) if value else None
    except (ValueError, TypeError):
        return None


async def check_drive_online(drive_letter: str) -> bool:
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


async def read_catalog_json(root_path: str) -> Optional[CatalogInfo]:
    catalog_path = os.path.join(root_path, "catalog.json")

    if not os.path.exists(catalog_path):
        return None

    try:
        import json

        with open(catalog_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return CatalogInfo(
            id=data.get("id", ""),
            name=data.get("name", ""),
            version=data.get("version", "1.0"),
            created=data.get("created", ""),
        )
    except Exception as e:
        print(f"Error reading catalog.json: {e}")
        return None


async def get_source_identifier(
    root_path: str,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    catalog_info = await read_catalog_json(root_path)

    if catalog_info and catalog_info.id:
        return catalog_info.id, None, catalog_info

    drive_letter = os.path.splitdrive(root_path)[0].rstrip(":")
    volume_label = await get_volume_label(drive_letter)

    if volume_label:
        return None, volume_label, None

    return None, None, None
