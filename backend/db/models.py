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


import json
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    TypeDecorator,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import DeclarativeMeta

# Creates a base class for declarative models using SQLAlchemy.
Base: DeclarativeMeta = declarative_base()

# Creates a MetaData object that holds schema-level information such as tables, columns, and constraints.
metadata = MetaData()


class AwareDateTime(TypeDecorator):
    """
    A type that ensures timezone-aware datetimes by
    attaching UTC if the datetime is naive.
    """

    impl = DateTime(timezone=False)  # or True, but SQLite doesn't honor tz anyway
    cache_ok = False

    def process_result_value(self, value, dialect):
        """
        When reading from DB, if it's naive, attach UTC.
        """
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def process_bind_param(self, value, dialect):
        """
        (Optional) When writing to DB, you can also
        enforce that all datetimes are stored in UTC.
        """
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class JsonField(TypeDecorator):
    """
    A type for handling JSON data by serializing/deserializing
    it during storage and retrieval.
    """

    impl = JSON

    def process_result_value(self, value, dialect):
        """
        When reading from DB, deserialize JSON string to Python object.
        """
        # Some dialects/DB drivers already return JSON columns as Python
        # objects (dict/list). Only decode when we receive a JSON string.
        if isinstance(value, (str, bytes, bytearray)):
            return json.loads(value)
        return value

    def process_bind_param(self, value, dialect):
        """
        When writing to DB, serialize Python object to JSON string.
        """
        if value is not None:
            return json.dumps(value)
        return value


class CameraType(str, PyEnum):
    WEBRTC = "webrtc"
    HLS = "hls"
    MJPEG = "mjpeg"


class SatelliteGroupType(str, PyEnum):
    USER = "user"
    SYSTEM = "system"


class SDRType(str, PyEnum):
    RTLSDRUSBV3 = "rtlsdrusbv3"
    RTLSDRTCPV3 = "rtlsdrtcpv3"
    RTLSDRUSBV4 = "rtlsdrusbv4"
    RTLSDRTCPV4 = "rtlsdrtcpv4"
    SOAPYSDRLOCAL = "soapysdrlocal"
    SOAPYSDRREMOTE = "soapysdrremote"
    UHD = "uhd"
    SIGMFPLAYBACK = "sigmfplayback"


class Satellites(Base):
    __tablename__ = "satellites"
    norad_id = Column(Integer, primary_key=True, nullable=False, unique=True)
    name = Column(String, nullable=False)
    source = Column(String, nullable=False, default="manual", server_default="manual")
    name_other = Column(String, nullable=True)
    alternative_name = Column(String, nullable=True)
    image = Column(String, nullable=True)
    sat_id = Column(String, nullable=True)
    tle1 = Column(String, nullable=False)
    tle2 = Column(String, nullable=False)
    status = Column(String, nullable=True)
    decayed = Column(AwareDateTime, nullable=True)
    launched = Column(AwareDateTime, nullable=True)
    deployed = Column(AwareDateTime, nullable=True)
    website = Column(String, nullable=True)
    operator = Column(String, nullable=True)
    countries = Column(String, nullable=True)
    citation = Column(String, nullable=True)
    is_frequency_violator = Column(Boolean, nullable=True, default=False)
    associated_satellites = Column(String, nullable=True)
    added = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated = Column(
        AwareDateTime,
        nullable=True,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )


class Transmitters(Base):
    __tablename__ = "transmitters"
    id = Column(String, nullable=False, primary_key=True, unique=True)
    description = Column(String, nullable=True)
    alive = Column(Boolean, nullable=True)
    type = Column(String, nullable=True)
    uplink_low = Column(Integer, nullable=True)
    uplink_high = Column(Integer, nullable=True)
    uplink_drift = Column(Integer, nullable=True)
    downlink_low = Column(Integer, nullable=True)
    downlink_high = Column(Integer, nullable=True)
    downlink_drift = Column(Integer, nullable=True)
    mode = Column(String, nullable=True)
    mode_id = Column(Integer, nullable=True)
    uplink_mode = Column(String, nullable=True)
    invert = Column(Boolean, nullable=True)
    baud = Column(Integer, nullable=True)
    sat_id = Column(String, nullable=True)
    norad_cat_id = Column(Integer, ForeignKey("satellites.norad_id"), nullable=False)
    norad_follow_id = Column(Integer, nullable=True)
    status = Column(String, nullable=False)
    citation = Column(String, nullable=True)
    service = Column(String, nullable=True)
    source = Column(String, nullable=True)
    iaru_coordination = Column(String, nullable=True)
    iaru_coordination_url = Column(String, nullable=True)
    itu_notification = Column(JSON, nullable=True)
    frequency_violation = Column(Boolean, nullable=True, default=False)
    unconfirmed = Column(Boolean, nullable=True, default=False)
    added = Column(AwareDateTime, nullable=True, default=datetime.now(timezone.utc))
    updated = Column(
        AwareDateTime,
        nullable=True,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )


class Rigs(Base):
    __tablename__ = "rigs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(String, nullable=False)
    host = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    radiotype = Column(String, nullable=False)
    radio_mode = Column(String, nullable=False, default="duplex", server_default="duplex")
    vfotype = Column(Integer, nullable=False)
    tx_control_mode = Column(String, nullable=False, default="auto", server_default="auto")
    retune_interval_ms = Column(Integer, nullable=False, default=2000, server_default="2000")
    follow_downlink_tuning = Column(Boolean, nullable=False, default=False, server_default="0")
    added = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated = Column(
        AwareDateTime,
        nullable=False,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )


class SDRs(Base):
    __tablename__ = "sdrs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(String, nullable=False)
    serial = Column(String, nullable=True)
    host = Column(String, nullable=True)
    port = Column(Integer, nullable=True)
    type = Column(Enum(SDRType), nullable=True)
    driver = Column(String, nullable=True)
    frequency_min = Column(Integer, nullable=True)
    frequency_max = Column(Integer, nullable=True)
    added = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated = Column(
        AwareDateTime,
        nullable=False,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )


class Rotators(Base):
    __tablename__ = "rotators"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(String, nullable=False)
    host = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    minaz = Column(Integer, nullable=False)
    maxaz = Column(Integer, nullable=False)
    azimuth_mode = Column(String, nullable=False, default="0_360")
    minel = Column(Integer, nullable=False)
    maxel = Column(Integer, nullable=False)
    parkaz = Column(Float, nullable=True)
    parkel = Column(Float, nullable=True)
    aztolerance = Column(Float, nullable=False, default=2.0)
    eltolerance = Column(Float, nullable=False, default=2.0)
    added = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated = Column(
        AwareDateTime,
        nullable=False,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )


class Locations(Base):
    __tablename__ = "locations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    alt = Column(Integer, nullable=False)
    added = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated = Column(
        AwareDateTime,
        nullable=True,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )


class Preferences(Base):
    __tablename__ = "preferences"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(String, nullable=False)
    value = Column(String, nullable=False)
    added = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated = Column(
        AwareDateTime,
        nullable=True,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )


class TLESources(Base):
    __tablename__ = "tle_sources"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(String, nullable=False)
    identifier = Column(String, nullable=False)
    url = Column(String, nullable=False)
    format = Column(String, nullable=False, default="3le")
    added = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated = Column(
        AwareDateTime,
        nullable=False,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )


class Groups(Base):
    __tablename__ = "groups"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(String, nullable=False)
    identifier = Column(String, nullable=True)
    type = Column(Enum(SatelliteGroupType), nullable=False, default=SatelliteGroupType.USER)
    satellite_ids = Column(JsonField, nullable=True)
    added = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated = Column(
        AwareDateTime,
        nullable=False,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )


class TrackingState(Base):
    __tablename__ = "tracking_state"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(String, index=True, unique=True)
    value = Column(JSON, index=True)
    added = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated = Column(
        AwareDateTime,
        nullable=True,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )


class Cameras(Base):
    __tablename__ = "cameras"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    name = Column(String, nullable=False)
    url = Column(String, nullable=True)
    type = Column(Enum(CameraType), nullable=False)
    status = Column(Enum("active", "inactive"), nullable=False, default="active")
    added = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated = Column(
        AwareDateTime,
        nullable=False,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )


class ObservationStatus(str, PyEnum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    MISSED = "missed"


# ============================================================================
# CHEMTRAIL TRACKER MODELS
# ============================================================================


class DetectionType(str, PyEnum):
    """Enum for detection types."""
    CONTRAIL = "contrail"
    AIRCRAFT = "aircraft"
    UNKNOWN = "unknown"


class ProcessingStatus(str, PyEnum):
    """Enum for processing job status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ChemtrailCameras(Base):
    """
    Extended camera model with geolocalization metadata for contrail tracking.

    Stores camera position, orientation, and optical characteristics needed
    for azimuth/elevation calculations and triangulation.
    """
    __tablename__ = "chemtrail_cameras"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    url = Column(String, nullable=True)  # RTSP/MJPEG URL or API endpoint
    type = Column(Enum(CameraType), nullable=False)

    # Geolocation (required for triangulation)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    altitude = Column(Float, nullable=False)  # meters AMSL

    # Orientation (required for az/el calculation)
    azimuth = Column(Float, nullable=False, default=0.0)  # 0-360 degrees
    elevation = Column(Float, nullable=False, default=0.0)  # -90 to 90 degrees

    # Optical characteristics
    fov_horizontal = Column(Float, nullable=True)  # degrees
    fov_vertical = Column(Float, nullable=True)  # degrees
    image_width = Column(Integer, nullable=True)
    image_height = Column(Integer, nullable=True)
    lens_distortion = Column(JSON, nullable=True)  # {k1, k2, p1, p2}

    # Operational
    status = Column(String, nullable=False, default="inactive")  # active, inactive, error
    last_image_at = Column(AwareDateTime, nullable=True)
    extra_data = Column(JSON, nullable=True)  # Renamed from 'metadata' (SQLAlchemy reserved)

    # Timestamps
    created_at = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(
        AwareDateTime,
        nullable=True,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc)
    )


class VideoCatalog(Base):
    """
    Video catalog for Phase 2 footage management.

    Stores metadata for all video sources (live webcams, historical files,
    YouTube archives) with weather enrichment and quality scoring.
    """
    __tablename__ = "video_catalog"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Source identification
    source_type = Column(String, nullable=False, index=True)  # webcam, local, youtube
    source_url = Column(String, nullable=True)
    local_path = Column(String, nullable=True)

    # Camera linkage
    camera_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    camera_name = Column(String, nullable=True)

    # Location
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    altitude = Column(Float, nullable=False)

    # Video properties
    title = Column(String, nullable=True)
    description = Column(String, nullable=True)
    duration_seconds = Column(Float, nullable=False)
    resolution = Column(String, nullable=False, default="unknown")  # 480p, 720p, 1080p, 4K
    codec = Column(String, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)

    # Quality scoring
    quality_score = Column(Float, nullable=False, default=0.0, index=True)  # 0-100
    quality_metrics = Column(JSON, nullable=True)  # {resolution_score, stability_score, lighting_score, sharpness_score}

    # Temporal
    recorded_at = Column(AwareDateTime, nullable=False, index=True)
    ingested_at = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))

    # Weather enrichment
    weather_data = Column(JSON, nullable=True)  # {temperature, cloud_cover, visibility, wind_speed, etc.}

    # Tags
    tags = Column(JSON, nullable=True)  # Custom tags for organization

    # Processing status
    processing_status = Column(String, nullable=False, default="pending", index=True)
    chunk_count = Column(Integer, nullable=False, default=0)
    detection_count = Column(Integer, nullable=False, default=0)
    error_message = Column(String, nullable=True)

    # Checksum for deduplication
    checksum_sha256 = Column(String, nullable=True, index=True)

    # Timestamps
    created_at = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(
        AwareDateTime,
        nullable=True,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc)
    )

    __table_args__ = (
        # Composite index for common queries
        Index("idx_video_catalog_camera_time", "camera_id", "recorded_at"),
        Index("idx_video_catalog_quality", "quality_score", postgresql_using="btree"),
        Index("idx_video_catalog_location", "latitude", "longitude"),
    )


class ChemtrailDetections(Base):
    """
    Core detection records linking cameras, flights, and observations.

    Stores contrail/aircraft detections with image-space coordinates,
    calculated azimuth/elevation, and estimated 3D position.
    """
    __tablename__ = "chemtrail_detections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign keys
    camera_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chemtrail_cameras.id"),
        nullable=False,
        index=True
    )
    icao24 = Column(
        String,
        ForeignKey("flight_cache.icao24"),
        nullable=True,
        index=True
    )

    # Detection type
    detection_type = Column(Enum(DetectionType), nullable=False, index=True)

    # Timing
    timestamp = Column(AwareDateTime, nullable=False, index=True)
    processing_latency_ms = Column(Integer, nullable=True)

    # Image reference
    image_path = Column(String, nullable=False)
    image_hash = Column(String, nullable=True, index=True)  # For deduplication

    # Detection location (image space)
    pixel_x = Column(Float, nullable=False)
    pixel_y = Column(Float, nullable=False)
    bounding_box = Column(JSON, nullable=True)  # [x1, y1, x2, y2] for aircraft

    # Calculated az/el from camera
    azimuth = Column(Float, nullable=False)
    elevation = Column(Float, nullable=False)

    # Estimated 3D position (WGS84)
    estimated_latitude = Column(Float, nullable=True, index=True)
    estimated_longitude = Column(Float, nullable=True, index=True)
    estimated_altitude = Column(Float, nullable=True)
    position_method = Column(String, nullable=True)  # "single_camera", "triangulation", "flight_correlation"

    # Detection quality
    confidence = Column(Float, nullable=False)  # 0.0-1.0
    correlation_score = Column(Float, nullable=True)  # 0.0-1.0 for flight match

    # Contrail-specific data
    contrail_vector = Column(JSON, nullable=True)  # {angle, length_px, width_px, persistence}

    # Processing metadata
    processing_metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(
        AwareDateTime,
        nullable=True,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc)
    )

    __table_args__ = (
        # Compound index for time-range queries by camera
        Index("idx_detections_camera_time", "camera_id", "timestamp"),
    )


class FlightCache(Base):
    """
    Cached flight data from OpenSky/FR24 APIs.

    Stores recent flight positions and history for correlation with detections.
    Supports dual-source data from both OpenSky and Flightradar24.
    """
    __tablename__ = "flight_cache"

    icao24 = Column(String, primary_key=True, nullable=False)
    callsign = Column(String, nullable=True, index=True)
    registration = Column(String, nullable=True)
    aircraft_type = Column(String, nullable=True)
    origin = Column(String, nullable=True)  # OpenSky origin_country
    destination = Column(String, nullable=True)

    # FR24-specific fields
    fr24_id = Column(String, nullable=True, index=True)  # FR24 flight ID
    squawk = Column(String, nullable=True)  # Transponder code
    vertical_rate = Column(Integer, nullable=True)  # Feet per minute
    painted_as = Column(String, nullable=True)  # Airline ICAO (branding)
    operating_as = Column(String, nullable=True)  # Airline ICAO (operator)
    eta = Column(AwareDateTime, nullable=True)  # Estimated time of arrival

    # FR24 airport codes (more detailed than origin/destination)
    origin_icao = Column(String, nullable=True)
    origin_iata = Column(String, nullable=True)
    destination_icao = Column(String, nullable=True)
    destination_iata = Column(String, nullable=True)

    # Current position (updated from API)
    position = Column(JSON, nullable=True)  # {lat, lon, alt, heading, velocity}
    last_position_update = Column(AwareDateTime, nullable=True, index=True)

    # Position history (for correlation with detections)
    position_history = Column(JSON, nullable=True)  # Array of {timestamp, lat, lon, alt}

    # Flight track data from FR24
    flight_track = Column(JSON, nullable=True)  # Array of track points from FR24

    # Raw API responses (for debugging/reprocessing)
    raw_message = Column(JSON, nullable=True)  # OpenSky raw response
    fr24_raw_message = Column(JSON, nullable=True)  # FR24 raw response

    # Data source tracking
    data_sources = Column(JSON, nullable=True)  # ["opensky", "fr24"] - which sources contributed

    # Timestamps
    first_seen = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(
        AwareDateTime,
        nullable=True,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc)
    )


class DetectionFrames(Base):
    """
    Time-series tracking data for moving detections (contrail evolution).
    """
    __tablename__ = "detection_frames"

    id = Column(Integer, primary_key=True, autoincrement=True)
    detection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chemtrail_detections.id"),
        nullable=False,
        index=True
    )
    frame_timestamp = Column(AwareDateTime, nullable=False, index=True)
    frame_sequence = Column(Integer, nullable=False)

    # Position in frame
    pixel_x = Column(Float, nullable=False)
    pixel_y = Column(Float, nullable=False)

    # Motion data
    velocity_x = Column(Float, nullable=True)
    velocity_y = Column(Float, nullable=True)

    # Blob/contour data (compressed)
    blob_data = Column(JSON, nullable=True)

    # Timestamp
    created_at = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))

    __table_args__ = (
        # Optimized for time-range queries
        Index("idx_frames_detection_time", "detection_id", "frame_timestamp"),
    )


class TriangulationResults(Base):
    """
    Results from multi-camera triangulation.
    """
    __tablename__ = "triangulation_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Linked detections
    detection_1_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chemtrail_detections.id"),
        nullable=False
    )
    detection_2_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chemtrail_detections.id"),
        nullable=False
    )

    # Camera baseline
    baseline_km = Column(Float, nullable=True)  # Distance between cameras

    # Result
    triangulated_latitude = Column(Float, nullable=False)
    triangulated_longitude = Column(Float, nullable=False)
    triangulated_altitude = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    intersection_angle = Column(Float, nullable=True)  # Quality metric

    # Method
    method = Column(String, nullable=False)  # "least_squares", "geometric", etc.

    # Timestamp
    created_at = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))


class MonitoredSatellites(Base):
    """
    Satellites monitored for automatic observation generation.
    Stores configuration templates used to generate scheduled observations.
    """

    __tablename__ = "monitored_satellites"

    # Identity & Query Keys
    id = Column(String, primary_key=True, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    norad_id = Column(
        Integer,
        ForeignKey("satellites.norad_id"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Hardware FKs (for referential integrity & "what's using this hardware?")
    sdr_id = Column(UUID(as_uuid=True), ForeignKey("sdrs.id"), nullable=True)
    rotator_id = Column(UUID(as_uuid=True), ForeignKey("rotators.id"), nullable=True)
    rig_id = Column(UUID(as_uuid=True), ForeignKey("rigs.id"), nullable=True)

    # Grouped config as JSON (flexible, maps to frontend structure)
    satellite_config = Column(JSON, nullable=False)  # {"name": "ISS (ZARYA)", "group_id": "..."}
    hardware_config = Column(JSON, nullable=False)  # {"rotator": {...}, "rig": {...}}
    generation_config = Column(JSON, nullable=False)  # {"min_elevation": 20, "lookahead_hours": 24}
    sessions = Column(
        JSON, nullable=False
    )  # [{"sdr": {...}, "tasks": [{"type": "iq_recording", "config": {}}]}]

    # Metadata
    created_at = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(
        AwareDateTime,
        nullable=False,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )


class ScheduledObservations(Base):
    """
    Individual scheduled observations for specific satellite passes.
    Can be created manually or auto-generated from MonitoredSatellites.
    """

    __tablename__ = "scheduled_observations"

    # Identity & Query Keys
    id = Column(String, primary_key=True, nullable=False)
    name = Column(String, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    status = Column(
        Enum(ObservationStatus),
        nullable=False,
        default=ObservationStatus.SCHEDULED,
        index=True,
    )
    norad_id = Column(Integer, ForeignKey("satellites.norad_id"), nullable=False, index=True)

    # Pass timing (critical for scheduling queries)
    event_start = Column(AwareDateTime, nullable=False, index=True)  # AOS - horizon crossing
    event_end = Column(AwareDateTime, nullable=False)  # LOS - horizon crossing
    task_start = Column(
        AwareDateTime, nullable=True, index=True
    )  # When tasks actually start (at elevation threshold)
    task_end = Column(
        AwareDateTime, nullable=True
    )  # When tasks actually end (usually same as event_end)

    # Hardware FKs
    sdr_id = Column(UUID(as_uuid=True), ForeignKey("sdrs.id"), nullable=True)
    rotator_id = Column(UUID(as_uuid=True), ForeignKey("rotators.id"), nullable=True)
    rig_id = Column(UUID(as_uuid=True), ForeignKey("rigs.id"), nullable=True)

    # Grouped config as JSON
    satellite_config = Column(JSON, nullable=False)  # {"name": "ISS (ZARYA)", "group_id": "..."}
    pass_config = Column(JSON, nullable=False)  # {"peak_altitude": 22.268358}
    hardware_config = Column(
        JSON, nullable=False
    )  # {"rotator": {...}, "rig": {...}, "transmitter": {...}}
    sessions = Column(
        JSON, nullable=False
    )  # [{"sdr": {...}, "tasks": [{"type": "iq_recording", "config": {}}]}]

    # Auto-generation tracking (nullable if manually created)
    monitored_satellite_id = Column(
        String,
        ForeignKey("monitored_satellites.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    generated_at = Column(AwareDateTime, nullable=True)

    # Error tracking
    error_message = Column(String, nullable=True)  # Last error message
    error_count = Column(Integer, nullable=False, default=0)  # Number of errors encountered
    last_error_time = Column(AwareDateTime, nullable=True)  # When last error occurred

    # Execution metadata
    actual_start_time = Column(AwareDateTime, nullable=True)  # When execution actually started
    actual_end_time = Column(AwareDateTime, nullable=True)  # When execution actually ended
    execution_log = Column(JSON, nullable=True)  # Array of timestamped events/errors

    # Metadata
    created_at = Column(AwareDateTime, nullable=False, default=datetime.now(timezone.utc))
    updated_at = Column(
        AwareDateTime,
        nullable=False,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )
