from __future__ import annotations

import asyncio
import base64
import json
import math
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from rwi_bot.ai.client import OpenAIUnavailableError, RwiOpenAIClient
from rwi_bot.domain.schemas import AuditRecord
from rwi_bot.services.audit import AuditService
from rwi_bot.services.budget import SpendingClass

_VIDEO_MIME_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/webm",
    "video/x-matroska",
    "video/x-msvideo",
}
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v", ".mkv", ".avi"}


class ReadableAttachment(Protocol):
    filename: str
    size: int
    content_type: str | None

    async def read(self, *, use_cached: bool = True) -> bytes: ...


class VideoInspectionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VideoProbe:
    duration_seconds: float
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class VideoInspectionOutcome:
    text: str
    duration_seconds: float
    sampled_frames: int
    start_seconds: float = 0
    media_kind: str = "video"


def inspection_window(question: str, duration: float, maximum: int = 45) -> tuple[float, float]:
    """Parse explicit timestamps, never interpret a gear/stat range as a time range."""
    stamp = r"(?:\d{1,2}:\d{2}(?::\d{2})?|\d+(?:\.\d+)?\s*(?:seconds?|secs?|s))"
    match = re.search(rf"({stamp})\s*(?:-|\u2013|\u2014|to|through)\s*({stamp})", question, re.I)
    # Explicit trailing units also allow natural requests such as "10 to 40 seconds".
    if match is None:
        match = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:-|to|through)\s*"
            r"(\d+(?:\.\d+)?\s*(?:seconds?|secs?|s))\b",
            question,
            re.I,
        )

    def seconds(value: str) -> float:
        if ":" in value:
            if any(int(part) >= 60 for part in value.split(":")[1:]):
                raise VideoInspectionError("Use valid timestamps, for example 1:10-1:40.")
            result = 0.0
            for part in value.split(":"):
                result = result * 60 + float(part)
            return result
        return float(re.sub(r"[^\d.]", "", value))

    start, end = 0.0, duration
    if match:
        start, end = seconds(match[1]), seconds(match[2])
    else:
        offset = re.search(rf"\b(?:from|starting at|start at)\s+({stamp})", question, re.I)
        if offset:
            start = seconds(offset[1])
    if not math.isfinite(duration) or duration <= 0 or start >= duration or end <= start:
        raise VideoInspectionError(
            "That time range is outside the recording. Give a range such as 1:10-1:40."
        )
    return start, min(end, duration, start + min(maximum, 45)) - start


class VideoInspectionService:
    """Privacy-bounded inspection for short, user-supplied gameplay recordings."""

    def __init__(
        self,
        *,
        ai: RwiOpenAIClient,
        audit: AuditService,
        enabled: bool,
        maximum_duration_seconds: int,
        maximum_bytes: int,
        sample_frames: int,
        ffmpeg_binary: str,
        ffprobe_binary: str,
    ) -> None:
        self.ai = ai
        self.audit = audit
        self.enabled = enabled
        self.maximum_duration_seconds = maximum_duration_seconds
        self.maximum_bytes = maximum_bytes
        self.sample_frames = sample_frames
        self.ffmpeg_binary = ffmpeg_binary
        self.ffprobe_binary = ffprobe_binary

    @staticmethod
    def supports_attachment(attachment: ReadableAttachment) -> bool:
        content_type = (attachment.content_type or "").split(";", maxsplit=1)[0].casefold()
        extension = Path(attachment.filename).suffix.casefold()
        return content_type in _VIDEO_MIME_TYPES or extension in _VIDEO_EXTENSIONS

    @staticmethod
    def supports_image(attachment: ReadableAttachment) -> bool:
        return Path(attachment.filename).suffix.casefold() in {".png", ".jpg", ".jpeg", ".webp"}

    async def inspect_image(
        self,
        attachment: ReadableAttachment,
        *,
        question: str,
        user_id: int,
        spending_class: SpendingClass = SpendingClass.MEMBER_ANSWER,
    ) -> VideoInspectionOutcome:
        if not self.enabled or not self.supports_image(attachment):
            raise VideoInspectionError("Screenshot inspection is unavailable for this file.")
        if attachment.size > min(self.maximum_bytes, 20_000_000):
            raise VideoInspectionError("Keep screenshots below 20 MB.")
        payload = await attachment.read(use_cached=True)
        if not payload or len(payload) > min(self.maximum_bytes, 20_000_000):
            raise VideoInspectionError("The screenshot exceeds the upload limit.")
        correlation_id = uuid4()
        with tempfile.TemporaryDirectory(prefix="erin-image-") as temporary:
            directory = Path(temporary)
            input_path = directory / ("upload" + Path(attachment.filename).suffix.casefold())
            await asyncio.to_thread(input_path.write_bytes, payload)
            filters = ["scale=1920:1920:force_original_aspect_ratio=decrease"]
            filters += [
                f"crop=iw*0.6:ih*0.6:iw*{x}:ih*{y},scale=1600:1600:force_original_aspect_ratio=decrease"
                for x, y in ((0, 0), (0.4, 0), (0, 0.4), (0.4, 0.4))
            ]
            frames = []
            for index, filter_ in enumerate(filters):
                output_path = directory / f"detail-{index}.jpg"
                await self._run_process(
                    self.ffmpeg_binary,
                    "-protocol_whitelist",
                    "file,pipe",
                    "-v",
                    "error",
                    "-max_pixels",
                    "40000000",
                    "-i",
                    str(input_path),
                    "-vf",
                    filter_,
                    "-frames:v",
                    "1",
                    str(output_path),
                )
                encoded = base64.b64encode(await asyncio.to_thread(output_path.read_bytes)).decode(
                    "ascii"
                )
                frames.append(f"data:image/jpeg;base64,{encoded}")
            try:
                answer = await self.ai.inspect_video_frames(
                    question=question
                    or "Read this Division 2 screenshot: gear, talents and visible values.",
                    frame_data_urls=tuple(frames),
                    timestamps=(0.0,) * len(frames),
                    user_id=user_id,
                    correlation_id=correlation_id,
                    media_kind="screenshot",
                    spending_class=spending_class,
                )
            except OpenAIUnavailableError as exc:
                raise VideoInspectionError(
                    "Screenshot analysis is temporarily unavailable; the upload was discarded."
                ) from exc
        await self.audit.record(
            AuditRecord(
                event_type="image.inspected",
                actor_id=user_id,
                target_type="ephemeral_screenshot",
                target_id=str(correlation_id),
                reason="Inspected screenshot and detail views; raw media discarded.",
                details={"raw_media_retained": False, "detail_views": len(frames)},
            )
        )
        text = (
            answer.text
            if answer.complete
            else "The visual analysis did not finish. Please ask about one part of the screenshot."
        )
        return VideoInspectionOutcome(text, 0, len(frames), media_kind="screenshot")

    async def inspect(
        self,
        attachment: ReadableAttachment,
        *,
        question: str,
        user_id: int,
    ) -> VideoInspectionOutcome:
        if not self.enabled:
            raise VideoInspectionError("Short gameplay-video inspection is currently disabled.")
        if not self.supports_attachment(attachment):
            raise VideoInspectionError(
                "I can inspect MP4, MOV, M4V, WebM, MKV, or AVI gameplay recordings."
            )
        if attachment.size > self.maximum_bytes:
            limit_mb = self.maximum_bytes // 1_000_000
            raise VideoInspectionError(
                f"That recording is too large. Keep it at or below {limit_mb} MB."
            )
        payload = await attachment.read(use_cached=True)
        if not payload or len(payload) > self.maximum_bytes:
            raise VideoInspectionError("The recording could not be read within the upload limit.")

        correlation_id = uuid4()
        with tempfile.TemporaryDirectory(prefix="erin-video-") as temporary:
            temporary_path = Path(temporary)
            suffix = Path(attachment.filename).suffix.casefold()
            if suffix not in _VIDEO_EXTENSIONS:
                suffix = ".mp4"
            input_path = temporary_path / f"upload{suffix}"
            await asyncio.to_thread(input_path.write_bytes, payload)
            probe = await self._probe(input_path)
            if probe.duration_seconds <= 0:
                raise VideoInspectionError("I could not determine a valid recording duration.")
            start, duration = inspection_window(
                question, probe.duration_seconds, self.maximum_duration_seconds
            )
            frame_paths = await self._extract_frames(
                input_path,
                temporary_path,
                duration=duration,
                start=start,
            )
            if len(frame_paths) < 2:
                raise VideoInspectionError(
                    "I could not extract enough readable gameplay frames from that recording."
                )
            frame_url_list: list[str] = []
            for path in frame_paths:
                frame_bytes = await asyncio.to_thread(path.read_bytes)
                encoded = base64.b64encode(frame_bytes).decode("ascii")
                frame_url_list.append(f"data:image/jpeg;base64,{encoded}")
            frame_urls = tuple(frame_url_list)
            timestamps: tuple[float, ...]
            if len(frame_paths) == 1:
                timestamps = (0.0,)
            else:
                step = duration / self.sample_frames
                timestamps = tuple(start + step * index for index in range(len(frame_paths)))
            try:
                answer = await self.ai.inspect_video_frames(
                    question=question.strip()
                    or "Describe what happens and identify any useful Division 2 mechanics shown.",
                    frame_data_urls=frame_urls,
                    timestamps=timestamps,
                    user_id=user_id,
                    correlation_id=correlation_id,
                )
            except OpenAIUnavailableError as exc:
                raise VideoInspectionError(
                    "I decoded the recording safely, but visual analysis is temporarily "
                    "unavailable. The upload was discarded; please try again later."
                ) from exc

        await self.audit.record(
            AuditRecord(
                event_type="video.inspected",
                actor_id=user_id,
                target_type="ephemeral_gameplay_video",
                target_id=str(correlation_id),
                reason="ERIN inspected a short gameplay recording; the upload was discarded.",
                correlation_id=correlation_id,
                details={
                    "duration_seconds": round(probe.duration_seconds, 2),
                    "window_start_seconds": start,
                    "analyzed_seconds": duration,
                    "sampled_frames": len(frame_paths),
                    "upload_bytes": len(payload),
                    "raw_media_retained": False,
                    "audio_analyzed": False,
                },
            )
        )
        text = answer.text
        if not answer.complete:
            text = "The visual analysis did not finish. Please ask me to focus on one moment."
        return VideoInspectionOutcome(
            text=text,
            duration_seconds=duration,
            sampled_frames=len(frame_paths),
            start_seconds=start,
        )

    async def _probe(self, input_path: Path) -> VideoProbe:
        output = await self._run_process(
            self.ffprobe_binary,
            "-protocol_whitelist",
            "file,pipe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height:format=duration",
            "-of",
            "json",
            str(input_path),
        )
        try:
            document = json.loads(output)
            stream = document["streams"][0]
            duration = float(document["format"]["duration"])
            width = int(stream["width"])
            height = int(stream["height"])
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise VideoInspectionError(
                "That file does not contain a readable video stream."
            ) from exc
        if width < 16 or height < 16 or width > 7680 or height > 4320:
            raise VideoInspectionError("That recording has unsupported frame dimensions.")
        return VideoProbe(duration_seconds=duration, width=width, height=height)

    async def _extract_frames(
        self,
        input_path: Path,
        output_dir: Path,
        *,
        duration: float,
        start: float = 0,
    ) -> list[Path]:
        frames_per_second = self.sample_frames / max(duration, 0.1)
        output_pattern = output_dir / "frame-%03d.jpg"
        await self._run_process(
            self.ffmpeg_binary,
            "-protocol_whitelist",
            "file,pipe",
            "-v",
            "error",
            "-ss",
            str(start),
            "-i",
            str(input_path),
            "-t",
            str(duration),
            "-vf",
            (
                f"fps={frames_per_second:.8f}:start_time=0,scale=1920:1080:force_original_aspect_ratio=decrease"
            ),
            "-frames:v",
            str(self.sample_frames),
            "-q:v",
            "3",
            str(output_pattern),
        )
        frame_paths = await asyncio.to_thread(lambda: sorted(output_dir.glob("frame-*.jpg")))
        return frame_paths[: self.sample_frames]

    @staticmethod
    async def _run_process(executable: str, *arguments: str) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                executable,
                *arguments,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            raise VideoInspectionError(
                "Video inspection is unavailable because the media decoder is not installed."
            ) from exc
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=45)
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            raise VideoInspectionError("The recording took too long to decode safely.") from exc
        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            raise VideoInspectionError(
                "The recording could not be decoded" + (f": {detail[:180]}" if detail else ".")
            )
        return stdout.decode("utf-8", errors="replace")
