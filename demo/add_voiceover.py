#!/usr/bin/env python3
"""
Generate plain-language narration for demo/sentinel-demo.mp4 using Edge TTS,
smooth fades + breathing gaps between scenes, duration matched to the actual video.

Default voice: en-US-GuyNeural (male). Override: EDGE_TTS_VOICE or --voice

  pip install -r requirements-demo.txt
  python demo/add_voiceover.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

SAMPLE_RATE = 48000
# Pause between spoken scenes — keep tight so narration tracks screen changes.
DEFAULT_SCENE_GAP_SEC = 0.06


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def ffprobe_duration(path: Path) -> float:
    r = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr or "ffprobe failed")
    data = json.loads(r.stdout)
    return float(data["format"]["duration"])


def _silence_wav(path: Path, sec: float) -> None:
    r = _run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r={SAMPLE_RATE}:cl=mono",
            "-t",
            f"{sec:.6f}",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            str(path),
        ]
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr or "ffmpeg silence failed")


def _segment_to_slot(src_mp3: Path, target_sec: float, out_wav: Path) -> None:
    """
    Fit TTS into a scene slot: gentle fades + pad so speech rarely ends on a hard chop.
    """
    target_sec = max(0.55, float(target_sec))
    samples = max(1, int(round(target_sec * SAMPLE_RATE)))
    fade_in = min(0.04, target_sec / 20)
    fade_out_d = min(0.12, max(0.04, target_sec * 0.03))
    st_out = max(0.0, target_sec - fade_out_d)

    filt = (
        f"aresample={SAMPLE_RATE},aformat=channel_layouts=mono,"
        f"afade=t=in:st=0:d={fade_in:.6f},"
        f"afade=t=out:st={st_out:.6f}:d={fade_out_d:.6f},"
        f"atrim=duration={target_sec:.6f},asetpts=PTS-STARTPTS,"
        f"apad=whole_len={samples}"
    )
    r = _run(["ffmpeg", "-y", "-i", str(src_mp3), "-af", filt, str(out_wav)])
    if r.returncode != 0:
        raise RuntimeError(r.stderr or "ffmpeg segment slot failed")


def _concat_wavs_list(paths: list[Path], out_wav: Path) -> None:
    lst = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    try:
        for p in paths:
            lst.write(f"file '{p.resolve()}'\n")
        lst.flush()
        r = _run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                lst.name,
                "-ar",
                str(SAMPLE_RATE),
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(out_wav),
            ]
        )
        if r.returncode != 0:
            raise RuntimeError(r.stderr or "ffmpeg concat failed")
    finally:
        Path(lst.name).unlink(missing_ok=True)


def _pad_tail_to_duration(audio_wav: Path, video_sec: float, out_wav: Path) -> None:
    """Extend narration with silence so mux matches full video length."""
    aud_sec = ffprobe_duration(audio_wav)
    pad_sec = video_sec - aud_sec
    if pad_sec <= 0.02:
        shutil.copy(audio_wav, out_wav)
        return
    pad_samples = max(1, int(round(pad_sec * SAMPLE_RATE)))
    filt = f"apad=pad_len={pad_samples}"
    r = _run(["ffmpeg", "-y", "-i", str(audio_wav), "-af", filt, str(out_wav)])
    if r.returncode != 0:
        raise RuntimeError(r.stderr or "ffmpeg tail pad failed")


def scaled_scene_slots(video_sec: float, gap_sec: float) -> list[float]:
    """Stretch/shrink storyboard weights so segments + gaps == video length."""
    from demo.demo_timings import SCENE_DURATIONS_SEC

    n = len(SCENE_DURATIONS_SEC)
    gap_budget = gap_sec * max(0, n - 1)
    budget = video_sec - gap_budget
    if budget <= 1.0:
        raise ValueError("Video too short for narration gaps — lower --gap")
    total_story = sum(SCENE_DURATIONS_SEC)
    scale = budget / total_story
    scaled = [d * scale for d in SCENE_DURATIONS_SEC]
    scaled[-1] += budget - sum(scaled)
    return scaled


async def _edge_tts_save(text: str, voice: str, rate: str, out_mp3: Path) -> None:
    import edge_tts

    comm = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    await comm.save(str(out_mp3))


async def build_narration(
    tmp: Path,
    voice: str,
    rate: str,
    video_sec: float,
    gap_sec: float,
) -> Path:
    from demo.voiceover_script import SCENE_SCRIPTS

    slots = scaled_scene_slots(video_sec, gap_sec)
    if len(SCENE_SCRIPTS) != len(slots):
        raise RuntimeError("voiceover_script: script count must match slots")

    segment_wavs: list[Path] = []
    for i, (text, slot_sec) in enumerate(zip(SCENE_SCRIPTS, slots, strict=True)):
        raw_mp3 = tmp / f"narr_{i:02d}.mp3"
        await _edge_tts_save(text, voice, rate, raw_mp3)
        seg_wav = tmp / f"narr_{i:02d}.wav"
        _segment_to_slot(raw_mp3, slot_sec, seg_wav)
        segment_wavs.append(seg_wav)

    gap_wav = tmp / "_gap.wav"
    _silence_wav(gap_wav, gap_sec)

    concat_list: list[Path] = []
    for i, seg in enumerate(segment_wavs):
        concat_list.append(seg)
        if i < len(segment_wavs) - 1:
            concat_list.append(gap_wav)

    merged = tmp / "narration_merged.wav"
    _concat_wavs_list(concat_list, merged)
    return merged


def mux(video: Path, audio_wav: Path, video_sec: float, output: Path) -> None:
    """Mux; use output -t so video length drives final file (no early cut)."""
    r = _run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(video),
            "-i",
            str(audio_wav),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-t",
            f"{video_sec:.6f}",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr or "ffmpeg mux failed")


def main() -> int:
    ap = argparse.ArgumentParser(description="Add smooth Edge TTS voiceover to Sentinel demo video.")
    ap.add_argument("--input", type=Path, default=_ROOT / "demo" / "sentinel-demo.mp4")
    ap.add_argument("--output", type=Path, default=_ROOT / "demo" / "sentinel-demo-narrated.mp4")
    ap.add_argument(
        "--voice",
        default=os.environ.get("EDGE_TTS_VOICE", "en-US-GuyNeural"),
        help="Edge TTS voice (default: en-US-GuyNeural).",
    )
    ap.add_argument(
        "--rate",
        default=os.environ.get("EDGE_TTS_RATE", "+6%"),
        help='Speaking rate hint, e.g. "-5%%" slower or "+0%%" (Edge TTS format).',
    )
    ap.add_argument(
        "--gap",
        type=float,
        default=float(os.environ.get("VOICEOVER_GAP_SEC", str(DEFAULT_SCENE_GAP_SEC))),
        help=f"Silence between scenes in seconds (default {DEFAULT_SCENE_GAP_SEC}).",
    )
    args = ap.parse_args()

    if shutil.which("ffmpeg") is None:
        print("ffmpeg not found — install with: brew install ffmpeg", file=sys.stderr)
        return 1
    if not args.input.is_file():
        print(f"Input video not found: {args.input}", file=sys.stderr)
        return 1
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        print("Missing edge-tts: pip install edge-tts", file=sys.stderr)
        return 1

    video_sec = ffprobe_duration(args.input)
    gap = max(0.0, args.gap)
    from demo.demo_timings import SCENE_DURATIONS_SEC as _dur

    n_scenes = len(_dur)
    max_gap = max(0.0, (video_sec - n_scenes * 0.5) / max(1, n_scenes - 1))
    if gap > max_gap:
        gap = max_gap
        print(f"Gap clamped to {gap:.3f}s so scenes have time to speak.", file=sys.stderr)

    slots = scaled_scene_slots(video_sec, gap)
    print(
        f"Video {video_sec:.2f}s · gap {gap:.2f}s · voice {args.voice} · rate {args.rate} · "
        f"slot range {min(slots):.2f}–{max(slots):.2f}s"
    )

    async def _go() -> Path:
        with tempfile.TemporaryDirectory(prefix="sentinel_vo_") as td:
            tmp = Path(td)
            merged = await build_narration(tmp, args.voice, args.rate, video_sec, gap)
            final_wav = tmp / "narration_padded.wav"
            _pad_tail_to_duration(merged, video_sec, final_wav)
            mux(args.input, final_wav, video_sec, args.output)
            return args.output

    asyncio.run(_go())

    if args.output.is_file():
        print(f"Done: {args.output}")
        return 0
    print("Output file missing.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
