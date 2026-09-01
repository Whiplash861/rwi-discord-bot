from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from rwi_bot.services.video_inspection import (
    VideoInspectionError,
    VideoInspectionService,
    VideoProbe,
)


class FakeAttachment:
    def __init__(
        self,
        *,
        filename: str = "gameplay.mp4",
        size: int = 100,
        content_type: str | None = "video/mp4",
    ) -> None:
        self.filename = filename
        self.size = size
        self.content_type = content_type

    async def read(self, *, use_cached: bool = True) -> bytes:
        assert use_cached is True
        return b"short-video"


def _service() -> VideoInspectionService:
    return VideoInspectionService(
        ai=cast(Any, SimpleNamespace()),
        audit=cast(Any, SimpleNamespace(record=AsyncMock())),
        enabled=True,
        maximum_duration_seconds=30,
        maximum_bytes=1_000_000,
        sample_frames=4,
        ffmpeg_binary="ffmpeg",
        ffprobe_binary="ffprobe",
    )


def test_video_detection_accepts_common_console_and_pc_formats() -> None:
    assert VideoInspectionService.supports_attachment(FakeAttachment(filename="clip.mp4"))
    assert VideoInspectionService.supports_attachment(
        FakeAttachment(filename="clip.webm", content_type=None)
    )
    assert VideoInspectionService.supports_attachment(
        FakeAttachment(filename="obs-recording.mkv", content_type="video/x-matroska")
    )
    assert not VideoInspectionService.supports_attachment(
        FakeAttachment(filename="notes.txt", content_type="text/plain")
    )


@pytest.mark.asyncio
async def test_probe_reads_verified_media_duration() -> None:
    service = _service()
    service._run_process = AsyncMock(  # type: ignore[method-assign]
        return_value=('{"streams":[{"width":1920,"height":1080}],"format":{"duration":"29.75"}}')
    )

    probe = await service._probe(Path("placeholder.mp4"))

    assert probe == VideoProbe(duration_seconds=29.75, width=1920, height=1080)


@pytest.mark.asyncio
async def test_video_over_30_seconds_is_rejected_before_ai_call() -> None:
    service = _service()
    service._probe = AsyncMock(  # type: ignore[method-assign]
        return_value=VideoProbe(duration_seconds=31.0, width=1920, height=1080)
    )

    with pytest.raises(VideoInspectionError, match="up to 30 seconds"):
        await service.inspect(FakeAttachment(), question="What happened?", user_id=42)


@pytest.mark.asyncio
async def test_successful_inspection_discards_media_and_records_no_filename() -> None:
    ai = SimpleNamespace(
        inspect_video_frames=AsyncMock(
            return_value=SimpleNamespace(text="Visible armor break at 4 seconds.", complete=True)
        )
    )
    audit = SimpleNamespace(record=AsyncMock())
    service = _service()
    service.ai = cast(Any, ai)
    service.audit = cast(Any, audit)
    service._probe = AsyncMock(  # type: ignore[method-assign]
        return_value=VideoProbe(duration_seconds=8.0, width=1280, height=720)
    )

    async def extract_frames(
        _input_path: Path,
        output_dir: Path,
        *,
        duration: float,
    ) -> list[Path]:
        assert duration == 8.0
        paths = [output_dir / "frame-001.jpg", output_dir / "frame-002.jpg"]
        await asyncio.gather(*(asyncio.to_thread(path.write_bytes, b"jpeg") for path in paths))
        return paths

    service._extract_frames = extract_frames  # type: ignore[method-assign]

    outcome = await service.inspect(
        FakeAttachment(filename="Austin-real-name-gameplay.mp4"),
        question="Why did my armor break?",
        user_id=42,
    )

    assert outcome.sampled_frames == 2
    assert "armor break" in outcome.text
    record = audit.record.await_args.args[0]
    assert record.details["raw_media_retained"] is False
    assert "filename" not in record.details
    call = ai.inspect_video_frames.await_args.kwargs
    assert call["timestamps"] == (0.0, 8.0)
