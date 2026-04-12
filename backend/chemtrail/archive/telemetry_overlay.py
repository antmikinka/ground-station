# Copyright (c) 2025 Efstratios Goudelis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Flight telemetry overlay for chemtrail detection clips.

Burns flight callsign, altitude, speed, heading, contrail vector, camera name,
and timestamp onto video clips using ffmpeg's ASS subtitle filter (libass).
"""

import functools
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime

from .chunker import _get_ffmpeg_executable, _get_video_duration


@functools.lru_cache(maxsize=1)
def _get_ass_ffmpeg() -> str:
    """Return an ffmpeg path that supports the ``ass`` subtitle filter.

    The system ffmpeg may be compiled without libass (common on macOS
    homebrew minimal installs). When that happens, fall back to the
    imageio-ffmpeg bundled binary which ships with libass enabled.
    """
    candidate = _get_ffmpeg_executable()
    try:
        r = subprocess.run(
            [candidate, "-filters"],
            capture_output=True, text=True, timeout=5,
        )
        if re.search(r"\bass\b.*V->V", r.stdout):
            return candidate
    except Exception:
        pass

    # system ffmpeg lacks libass, try imageio-ffmpeg
    try:
        import imageio_ffmpeg  # type: ignore
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass

    # last resort, return what we have and let ffmpeg error naturally
    return candidate


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_flight_metadata(
    icao24: str,
    flight_service,
    timestamp: datetime,
) -> dict | None:
    """Get flight metadata for overlay from OpenSky cache.

    Args:
        icao24: Flight ICAO24 hex code
        flight_service: FlightService instance
        timestamp: Detection timestamp

    Returns:
        Dict with flight data fields or None if not found
    """
    flight_data = flight_service.get_flight(icao24)
    if not flight_data:
        return None

    position = flight_data.get("position", {})

    return {
        "callsign": flight_data.get("callsign", "UNKNOWN"),
        "altitude": position.get("alt"),
        "velocity": position.get("velocity"),
        "heading": position.get("heading"),
        "latitude": position.get("lat"),
        "longitude": position.get("lon"),
        "timestamp": timestamp,
    }


def reverse_geocode(lat: float, lon: float) -> dict | None:
    """Reverse-geocode *lat*/*lon* into ``{"city": ..., "road": ...}``.

    Uses geopy + Nominatim. Returns ``None`` when geopy is not installed
    or the lookup fails. Results are cached by coordinates rounded to
    4 decimal places (~11 m precision).
    """
    try:
        from geopy.geoculators import Nominatim
    except ImportError:
        return None

    rounded = (round(lat, 4), round(lon, 4))
    return _geocode_cached(rounded)


@functools.lru_cache(maxsize=64)
def _geocode_cached(coords: tuple[float, float]) -> dict | None:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderServiceError

    time.sleep(1)  # respect Nominatim rate limit
    try:
        geolocator = Nominatim(user_agent="chemtrail")
        location = geolocator.reverse(coords, language="en", timeout=5)
    except (GeocoderServiceError, Exception):
        return None

    if location is None:
        return None

    addr = location.raw.get("address", {})
    city = (
        addr.get("city")
        or addr.get("town")
        or addr.get("village")
        or addr.get("county", "")
    )
    road = addr.get("road", "")
    return {"city": city, "road": road}


# ---------------------------------------------------------------------------
# Overlay rendering
# ---------------------------------------------------------------------------

# ASS colour constants (&HAABBGGRR format)
_WHITE = "&H00FFFFFF"
_LIGHT_GRAY = "&H00CCCCCC"
_DIM_GRAY = "&H00888888"
_YELLOW = "&H00FFFF00"
_CYAN = "&H00FFFF00"
_SHADOW_COL = "&H80000000"


def _secs_to_ass_time(s: float) -> str:
    """Convert seconds to ASS timestamp ``H:MM:SS.cc``."""
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{h}:{m:02d}:{sec:05.2f}"


def _get_video_dimensions(video_path: str) -> tuple[int, int]:
    """Return (width, height) of a video using ffmpeg."""
    ffmpeg_exe = _get_ffmpeg_executable()
    r = subprocess.run(
        [ffmpeg_exe, "-i", video_path],
        capture_output=True, text=True,
    )
    m = re.search(r"(\d{2,5})x(\d{2,5})", r.stderr)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 1280, 720


def _build_flight_overlay(
    metadata: dict,
    clip_duration: float,
    video_width: int,
    video_height: int,
) -> str:
    """Generate ASS subtitle content for flight data overlay.

    Layout (top-left):
        [CALLSIGN]
        Alt: XXXXX ft | Spd: XXX kts | Hdg: XXX

        YYYY-MM-DD HH:MM:SS UTC
        Lat: XX.XXXX Lon: XXX.XXXX

    Args:
        metadata: Flight metadata dict with keys:
                  callsign, altitude, velocity, heading, latitude, longitude, timestamp
        clip_duration: Duration of video clip in seconds
        video_width: Video width in pixels
        video_height: Video height in pixels

    Returns:
        ASS subtitle script content
    """
    scale = min(video_width / 1280, video_height / 720)

    # Position (top-left)
    x = int(20 * scale)
    y = int(30 * scale)
    line_height = int(25 * scale)

    # Font sizes
    callsign_fs = int(28 * scale)
    info_fs = int(18 * scale)
    coord_fs = int(14 * scale)

    end_time = _secs_to_ass_time(clip_duration + 1)

    # ASS styles
    styles = [
        f"Style: Callsign,Arial,{callsign_fs},{_YELLOW},&H00000000,"
        f"&H80000000,1,0,0,0,100,100,0,0,1,1,1,5,10,10,0,1",
        f"Style: Info,Arial,{info_fs},{_WHITE},&H00000000,"
        f"&H80000000,0,0,0,0,100,100,0,0,1,0.8,0.5,5,8,8,0,1",
        f"Style: Coords,Arial,{coord_fs},{_LIGHT_GRAY},&H00000000,"
        f"&H80000000,0,0,0,0,100,100,0,0,1,0,0,5,6,6,0,1",
    ]

    events = []

    # Callsign
    callsign = metadata.get("callsign", "UNKNOWN")
    events.append(
        f"Dialogue: 0,0:00:00.00,{end_time},Callsign,,"
        f"{{\\an7\\pos({x},{y})}}{callsign}"
    )

    # Flight info
    alt = metadata.get("altitude")
    velocity = metadata.get("velocity")
    heading = metadata.get("heading")

    alt_str = f"{int(alt)} ft" if alt is not None else "N/A"
    spd_str = f"{int(velocity * 1.944)} kts" if velocity is not None else "N/A"  # m/s to knots
    hdg_str = f"{int(heading)}°" if heading is not None else "N/A"

    info_y = y + line_height
    events.append(
        f"Dialogue: 0,0:00:00.00,{end_time},Info,,"
        f"{{\\an7\\pos({x},{info_y})}}Alt: {alt_str} | Spd: {spd_str} | Hdg: {hdg_str}"
    )

    # Timestamp and coordinates
    ts = metadata.get("timestamp")
    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S UTC") if ts else "Unknown"
    lat = metadata.get("latitude")
    lon = metadata.get("longitude")

    lat_str = f"{lat:.4f}" if lat is not None else "N/A"
    lon_str = f"{lon:.4f}" if lon is not None else "N/A"

    coord_y = info_y + line_height + int(10 * scale)
    events.append(
        f"Dialogue: 0,0:00:00.00,{end_time},Coords,,"
        f"{{\\an7\\pos({x},{coord_y})}}{ts_str}"
    )
    events.append(
        f"Dialogue: 0,0:00:00.00,{end_time},Coords,,"
        f"{{\\an7\\pos({x},{coord_y + line_height})}}Lat: {lat_str} Lon: {lon_str}"
    )

    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {video_width}\n"
        f"PlayResY: {video_height}\n"
        "ScaledBorderAndShadow: yes\n"
        "\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        + "\n".join(styles)
        + "\n\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text\n"
        + "\n".join(events)
        + "\n"
    )


def build_hud_overlay(
    flight_data: dict,
    camera_name: str,
    timestamp: datetime,
    contrail_vector: dict | None = None,
) -> dict:
    """Build a complete HUD metadata dict for overlay.

    Args:
        flight_data: Flight info with callsign, altitude, velocity, heading, lat, lon
        camera_name: Human-readable camera name
        timestamp: Detection timestamp
        contrail_vector: Optional contrail vector data

    Returns:
        Dict with all fields needed for _build_flight_overlay
    """
    metadata = {
        "callsign": flight_data.get("callsign", "UNKNOWN"),
        "altitude": flight_data.get("altitude"),
        "velocity": flight_data.get("velocity"),
        "heading": flight_data.get("heading"),
        "latitude": flight_data.get("latitude"),
        "longitude": flight_data.get("longitude"),
        "timestamp": timestamp,
        "camera_name": camera_name,
    }

    if contrail_vector:
        metadata["contrail_vector"] = contrail_vector

    return metadata


def apply_flight_overlay(
    input_path: str,
    output_path: str,
    flight_metadata: dict,
) -> str:
    """Burn flight data HUD onto detection clip.

    Args:
        input_path: Path to input video clip
        output_path: Path for output video with overlay
        flight_metadata: Dict with flight data from get_flight_metadata()

    Returns:
        output_path on success, input_path on failure
    """
    try:
        ffmpeg_exe = _get_ass_ffmpeg()
        width, height = _get_video_dimensions(input_path)
        clip_duration = _get_video_duration(input_path)
    except Exception:
        # Return input path on failure (file doesn't exist, ffmpeg error, etc.)
        return input_path

    ass_content = _build_flight_overlay(
        metadata=flight_metadata,
        clip_duration=clip_duration,
        video_width=width,
        video_height=height,
    )

    ass_fd, ass_path = tempfile.mkstemp(suffix=".ass", prefix="chemtrail_")
    try:
        with os.fdopen(ass_fd, "w") as f:
            f.write(ass_content)

        escaped = ass_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        vf = f"ass={escaped}"

        for codec_args in (
            ["-c:v", "libx264", "-crf", "18"],
            ["-c:v", "mpeg4", "-q:v", "5"],
        ):
            result = subprocess.run(
                [
                    ffmpeg_exe, "-y",
                    "-i", input_path,
                    "-vf", vf,
                    *codec_args,
                    "-c:a", "copy",
                    output_path,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and os.path.isfile(output_path):
                return output_path
    finally:
        try:
            os.unlink(ass_path)
        except OSError:
            pass

    return input_path
