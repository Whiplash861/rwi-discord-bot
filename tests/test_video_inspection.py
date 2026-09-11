from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from rwi_bot.services.video_inspection import (
    VideoInspectionError,
    VideoInspectionService,
    VideoProbe,
    inspection_window,
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
        maximum_duration_seconds=45,
        maximum_bytes=1_000_000,
        sample_frames=4,
        ffmpeg_binary="ffmpeg",
        ffprobe_binary="ffprobe",
    )


@pytest.mark.skipif(
    not shutil.which("ffmpeg"), reason="real media decoder runs in Docker validation"
)
@pytest.mark.asyncio
async def test_real_decoder_inspects_screenshot_and_clips_long_recording(tmp_path):
    screenshot = tmp_path / "fixture.png"
    video = tmp_path / "fixture.mp4"
    await asyncio.to_thread(
        subprocess.run,
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=blue:s=320x180",
            "-frames:v",
            "1",
            "-threads",
            "1",
            str(screenshot),
        ],
        check=True,
    )
    await asyncio.to_thread(
        subprocess.run,
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=red:s=320x180:r=4",
            "-t",
            "90",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            str(video),
        ],
        check=True,
    )
    service = _service()
    service.sample_frames = 18
    service.ai = SimpleNamespace(
        inspect_video_frames=AsyncMock(
            return_value=SimpleNamespace(text="Complete fixture analysis.", complete=True)
        )
    )

    class Attachment:
        def __init__(self, path):
            self.path = path
            self.filename = path.name
            self.size = path.stat().st_size
            self.content_type = "image/png" if path.suffix == ".png" else "video/mp4"

        async def read(self, *, use_cached=True):
            return self.path.read_bytes()

    image = await service.inspect_image(
        Attachment(screenshot), question="Inspect the stats", user_id=1
    )
    assert image.sampled_frames == 5
    assert image.media_kind == "screenshot"
    clip = await service.inspect(Attachment(video), question="inspect 1:00-1:30", user_id=1)
    assert clip.start_seconds == 60
    assert clip.duration_seconds == 30
    assert 2 <= clip.sampled_frames <= 18
    args = service.ai.inspect_video_frames.await_args.kwargs
    assert min(args["timestamps"]) == 60
    assert max(args["timestamps"]) < 90


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


@pytest.mark.parametrize(
    "question,duration,expected",
    [
        ("What happened?", 300, (0, 45)),
        ("What happened?", 31, (0, 31)),
        ("Inspect 1:10-1:40", 180, (70, 30)),
        ("Inspect 20s to 90s", 180, (20, 45)),
        ("Inspect 10 to 40 seconds", 180, (10, 30)),
        ("Starting at 1:10", 80, (70, 10)),
        ("I have 30-40 crit damage", 60, (0, 45)),
    ],
)
def test_clip_window_is_bounded(question, duration, expected) -> None:
    assert inspection_window(question, duration) == expected


@pytest.mark.parametrize(
    "question,duration",
    [("1:10-1:00", 80), ("2:00-2:10", 45), ("1:80-2:90", 400), ("", float("nan"))],
)
def test_invalid_clip_range_is_rejected(question, duration) -> None:
    with pytest.raises(VideoInspectionError):
        inspection_window(question, duration)


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
        start: float,
    ) -> list[Path]:
        assert duration == 8.0
        assert start == 0
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
    assert call["timestamps"] == (0.0, 2.0)
