"""Real-time scan progress tracking with SSE support."""

import asyncio
import time
from typing import AsyncGenerator, Optional
import logging

logger = logging.getLogger(__name__)


class ScanProgress:
    """Holds the current state of a scan operation."""

    def __init__(self, source_id: int, source_name: str, total_files: int):
        self.source_id = source_id
        self.source_name = source_name
        self.total_files = total_files
        self.processed = 0
        self.imported = 0
        self.confirmed = 0
        self.covers_found = 0
        self.missing = 0
        self.current_file = ""
        self.status = "starting"
        self.logs: list = []
        self.missing_books: list = []
        self.started_at = time.time()
        self.error_message: Optional[str] = None

    @property
    def percentage(self) -> int:
        if self.total_files == 0:
            return 0
        return int((self.processed / self.total_files) * 100)

    @property
    def elapsed(self) -> float:
        return time.time() - self.started_at

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "status": self.status,
            "percentage": self.percentage,
            "total_files": self.total_files,
            "processed": self.processed,
            "imported": self.imported,
            "confirmed": self.confirmed,
            "covers_found": self.covers_found,
            "missing": self.missing,
            "current_file": self.current_file,
            "logs": self.logs[-50:],
            "missing_books": self.missing_books,
            "elapsed": round(self.elapsed, 1),
            "error_message": self.error_message,
        }


class ScanProgressTracker:
    """In-memory tracker for concurrent scan operations, keyed by source_id."""

    def __init__(self):
        self._progress: dict = {}
        self._queues: dict = {}
        self._lock = asyncio.Lock()

    async def start(self, source_id: int, source_name: str, total_files: int):
        async with self._lock:
            self._progress[source_id] = ScanProgress(source_id, source_name, total_files)
            self._queues[source_id] = asyncio.Queue()
            logger.info("Started tracking source_id=%s, queue created", source_id)
            await self._queues[source_id].put({"event": "start", "data": self._progress[source_id].to_dict()})

    async def update(self, source_id: int, processed: int, imported: int = 0, confirmed: int = 0, covers_found: int = 0, current_file: str = "", log_message: str = "", status: str = ""):
        async with self._lock:
            p = self._progress.get(source_id)
            if not p:
                return
            p.processed = processed
            p.imported = imported  # Replace, not accumulate
            p.confirmed = confirmed  # Replace, not accumulate
            p.covers_found = covers_found  # Replace, not accumulate
            p.current_file = current_file
            if status:
                p.status = status
            if log_message:
                p.logs.append(log_message)
            await self._queues[source_id].put({"event": "update", "data": p.to_dict()})

    async def complete(self, source_id: int, missing: int = 0, missing_books: list | None = None,
                        imported: int = 0, confirmed: int = 0, covers_found: int = 0):
        async with self._lock:
            p = self._progress.get(source_id)
            if not p:
                return
            p.status = "complete"
            p.processed = p.total_files
            p.imported = imported  # Set final values
            p.confirmed = confirmed
            p.covers_found = covers_found
            p.missing = missing
            p.missing_books = missing_books or []
            await self._queues[source_id].put({"event": "complete", "data": p.to_dict()})

    async def error(self, source_id: int, error_message: str):
        async with self._lock:
            p = self._progress.get(source_id)
            if not p:
                return
            p.status = "error"
            p.error_message = error_message
            await self._queues[source_id].put({"event": "error", "data": p.to_dict()})

    async def cleanup(self, source_id: int):
        async with self._lock:
            self._progress.pop(source_id, None)
            self._queues.pop(source_id, None)

    def get_progress(self, source_id: int) -> dict | None:
        p = self._progress.get(source_id)
        return p.to_dict() if p else None

    async def event_stream(self, source_id: int):
        import json
        queue = self._queues.get(source_id)
        if not queue:
            logger.error("No queue for source_id=%s", source_id)
            yield 'event: error\ndata: {"error": "No scan in progress"}\n\n'
            return
        logger.info("SSE stream started for source_id=%s", source_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                event_type = event["event"]
                data_json = json.dumps(event["data"], ensure_ascii=False, default=str)
                logger.info("SSE sending event=%s for source_id=%s", event_type, source_id)
                yield f"event: {event_type}\ndata: {data_json}\n\n"
                if event_type in ("complete", "error"):
                    await asyncio.sleep(3)
                    break
        except Exception as e:
            logger.error("SSE stream error for source_id=%s: %s", source_id, e)
        logger.info("SSE stream ended for source_id=%s", source_id)


tracker = ScanProgressTracker()
