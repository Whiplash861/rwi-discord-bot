from __future__ import annotations

import asyncio
import base64
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from rwi_bot.ai.client import OpenAIUnavailableError, RwiOpenAIClient
from rwi_bot.domain.schemas import AuditRecord
from rwi_bot.services.audit import AuditService

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
            if probe.duration_seconds > self.maximum_duration_seconds + 0.25:
                raise VideoInspectionError(
                    f"I can inspect up to {self.maximum_duration_seconds} seconds at a time; "
                    f"this recording is about {probe.duration_seconds:.1f} seconds."
                )
            frame_paths = await self._extract_frames(
                input_path,
                temporary_path,
                duration=probe.duration_seconds,
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
                step = probe.duration_seconds / (len(frame_paths) - 1)
                timestamps = tuple(step * index for index in range(len(frame_paths)))
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
                    "sampled_frames": len(frame_paths),
                    "upload_bytes": len(payload),
                    "raw_media_retained": False,
                    "audio_analyzed": False,
                },
            )
        )
        text = answer.text
        if not answer.complete:
            text += "\n\n*The inspection response was truncated; ask me to focus on one moment.*"
        return VideoInspectionOutcome(
            text=text,
            duration_seconds=probe.duration_seconds,
            sampled_frames=len(frame_paths),
        )

    async def _probe(self, input_path: Path) -> VideoProbe:
        output = await self._run_process(
            self.ffprobe_binary,
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
    ) -> list[Path]:
        frames_per_second = self.sample_frames / max(duration, 0.1)
        output_pattern = output_dir / "frame-%03d.jpg"
        await self._run_process(
            self.ffmpeg_binary,
            "-v",
            "error",
            "-i",
            str(input_path),
            "-vf",
            (f"fps={frames_per_second:.8f},scale=1280:-2:force_original_aspect_ratio=decrease"),
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
