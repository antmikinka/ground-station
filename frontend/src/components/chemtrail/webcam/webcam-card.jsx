/**
 * @license
 * Copyright (c) 2025 Efstratios Goudelis
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program. If not, see <https://www.gnu.org/licenses/>.
 *
 */

import React, { useState, useEffect, useRef } from 'react';
import {
    Card,
    CardContent,
    CardActions,
    CardHeader,
    Typography,
    Chip,
    IconButton,
    Box,
    CircularProgress,
    Tooltip,
    Avatar,
    AvatarGroup,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import SatelliteAltIcon from '@mui/icons-material/SatelliteAlt';
import { useDispatch, useSelector } from 'react-redux';
import { useSocket } from '../../common/socket.jsx';
import {
    startLivePipeline,
    stopLivePipeline,
} from '../pipeline/pipeline-slice.js';
import { toast } from '../../../utils/toast-with-timestamp.jsx';

/**
 * MJPEG Stream Player - continuously fetches MJPEG frames and renders in img
 * Works with MJPEG streams by keeping a persistent HTTP connection
 */
const MjpegPlayer = ({ url, onFrameError, style }) => {
    const imgRef = useRef(null);
    const [error, setError] = useState(false);
    const [loaded, setLoaded] = useState(false);

    useEffect(() => {
        if (!url || !imgRef.current) return;

        setError(false);
        setLoaded(false);

        const img = imgRef.current;
        // Add cache-buster to force fresh connection
        img.src = `${url}${url.includes('?') ? '&' : '?'}_t=${Date.now()}`;

        const handleLoad = () => setLoaded(true);
        const handleError = () => {
            setError(true);
            if (onFrameError) onFrameError();
        };

        img.addEventListener('load', handleLoad);
        img.addEventListener('error', handleError);

        return () => {
            img.removeEventListener('load', handleLoad);
            img.removeEventListener('error', handleError);
            img.src = '';
        };
    }, [url]);

    const handleRefresh = () => {
        if (imgRef.current) {
            imgRef.current.src = `${url}${url.includes('?') ? '&' : '?'}_t=${Date.now()}`;
            setError(false);
            setLoaded(false);
        }
    };

    return (
        <Box
            sx={{
                position: 'relative',
                width: '100%',
                height: '100%',
                bgcolor: 'background.default',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                overflow: 'hidden',
            }}
        >
            <img
                ref={imgRef}
                style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'contain',
                    display: loaded ? 'block' : 'none',
                    ...style,
                }}
                alt="Live webcam feed"
            />
            {!loaded && !error && (
                <Box sx={{ position: 'absolute' }}>
                    <CircularProgress size={32} />
                </Box>
            )}
            {error && (
                <Box
                    sx={{
                        position: 'absolute',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: 1,
                    }}
                >
                    <Typography variant="caption" color="text.secondary">
                        Stream unavailable
                    </Typography>
                    <IconButton size="small" onClick={handleRefresh} color="primary">
                        <RefreshIcon fontSize="small" />
                    </IconButton>
                </Box>
            )}
        </Box>
    );
};

/**
 * Placeholder for cameras without a web-viewable stream
 */
const StreamPlaceholder = ({ camera }) => (
    <Box
        sx={{
            width: '100%',
            height: '100%',
            bgcolor: 'background.default',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 1,
        }}
    >
        <SatelliteAltIcon sx={{ fontSize: 48, color: 'text.disabled' }} />
        <Typography variant="caption" color="text.disabled" textAlign="center" sx={{ px: 2 }}>
            {camera.type === 'webrtc' ? 'WebRTC stream' : `${camera.type?.toUpperCase() || 'Stream'} not supported in grid view`}
        </Typography>
    </Box>
);

/**
 * Individual webcam camera card component
 */
export default function WebcamCard({ camera, pipelineRunning, pipelineCameraId }) {
    const { socket } = useSocket();
    const dispatch = useDispatch();
    const [showOverlay, setShowOverlay] = useState(false);
    const [hovered, setHovered] = useState(false);

    const isThisCameraRunning = pipelineRunning && pipelineCameraId === camera.id;
    const statusColor = isThisCameraRunning ? 'success' : camera.status === 'active' ? 'primary' : 'default';
    const statusLabel = isThisCameraRunning ? 'Processing' : camera.status || 'inactive';

    // For MJPEG cameras, we can show the stream directly
    const isMjpeg = camera.type === 'mjpeg';

    // Detection overlay - would show latest detection image overlaid on the feed
    const latestDetection = useSelector(
        (state) => state.chemtrailWebcam?.latestDetections?.[camera.id]
    );

    return (
        <Card
            sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                position: 'relative',
                transition: 'transform 0.2s, box-shadow 0.2s',
                ...(hovered && {
                    transform: 'translateY(-2px)',
                    boxShadow: (t) => t.shadows[8],
                }),
            }}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
        >
            <CardHeader
                title={camera.name || 'Unnamed Camera'}
                subheader={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5 }}>
                        {camera.latitude && camera.longitude && (
                            <Typography variant="caption" color="text.secondary">
                                <LocationOnIcon sx={{ fontSize: 12, verticalAlign: 'middle' }} />
                                {camera.latitude.toFixed(2)}, {camera.longitude.toFixed(2)}
                            </Typography>
                        )}
                    </Box>
                }
                avatar={
                    <Chip
                        label={statusLabel}
                        size="small"
                        color={statusColor}
                        variant={isThisCameraRunning ? 'filled' : 'outlined'}
                    />
                }
                sx={{ pb: 0, pt: 1 }}
            />

            {/* Video feed area */}
            <Box sx={{ position: 'relative', width: '100%', pt: '56.25%' /* 16:9 */ }}>
                <Box
                    sx={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                    }}
                >
                    {isMjpeg && camera.url ? (
                        <MjpegPlayer url={camera.url} />
                    ) : (
                        <StreamPlaceholder camera={camera} />
                    )}

                    {/* Detection overlay */}
                    {latestDetection && latestDetection.image_url && (
                        <Box
                            sx={{
                                position: 'absolute',
                                bottom: 8,
                                right: 8,
                                width: 120,
                                height: 90,
                                borderRadius: 1,
                                overflow: 'hidden',
                                border: '2px solid',
                                borderColor: 'warning.main',
                                boxShadow: (t) => t.shadows[3],
                                bgcolor: 'black',
                            }}
                        >
                            <img
                                src={latestDetection.image_url}
                                alt="Latest detection"
                                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                            />
                        </Box>
                    )}

                    {/* Pipeline processing indicator */}
                    {isThisCameraRunning && (
                        <Box
                            sx={{
                                position: 'absolute',
                                top: 8,
                                left: 8,
                                display: 'flex',
                                alignItems: 'center',
                                gap: 0.5,
                                bgcolor: 'rgba(76, 175, 80, 0.85)',
                                color: 'white',
                                borderRadius: 1,
                                px: 1,
                                py: 0.5,
                                fontSize: '0.7rem',
                                fontWeight: 600,
                            }}
                        >
                            <CircularProgress size={12} thickness={4} sx={{ color: 'white' }} />
                            LIVE
                        </Box>
                    )}
                </Box>
            </Box>

            <CardContent sx={{ pt: 1, pb: 0.5, flexGrow: 1 }}>
                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                    {camera.azimuth != null && (
                        <Chip label={`Az: ${camera.azimuth.toFixed(0)}°`} size="small" variant="outlined" sx={{ fontSize: '0.65rem' }} />
                    )}
                    {camera.elevation != null && (
                        <Chip label={`El: ${camera.elevation.toFixed(0)}°`} size="small" variant="outlined" sx={{ fontSize: '0.65rem' }} />
                    )}
                    {camera.fov_horizontal != null && (
                        <Chip label={`FOV: ${camera.fov_horizontal}°`} size="small" variant="outlined" sx={{ fontSize: '0.65rem' }} />
                    )}
                </Box>
            </CardContent>

            <CardActions sx={{ pt: 0, px: 2, pb: 1 }}>
                {/* Start/Stop pipeline button */}
                {isThisCameraRunning ? (
                    <Tooltip title="Stop live processing">
                        <IconButton
                            size="small"
                            color="error"
                            onClick={() => {
                                dispatch(stopLivePipeline({ socket }))
                                    .unwrap()
                                    .then(() => toast.success('Live pipeline stopped'))
                                    .catch((err) => toast.error(err.message));
                            }}
                        >
                            <StopIcon />
                        </IconButton>
                    </Tooltip>
                ) : !pipelineRunning ? (
                    <Tooltip title="Start live processing for this camera">
                        <IconButton
                            size="small"
                            color="success"
                            onClick={() => {
                                dispatch(startLivePipeline({
                                    socket,
                                    cameraId: camera.id,
                                    durationHours: 1,
                                    chunkInterval: 30,
                                    skipStill: true,
                                    applyOverlay: false,
                                }))
                                    .unwrap()
                                    .then(() => toast.success(`Live pipeline started for ${camera.name}`))
                                    .catch((err) => toast.error(err.message));
                            }}
                        >
                            <PlayArrowIcon />
                        </IconButton>
                    </Tooltip>
                ) : (
                    <Tooltip title={`Pipeline running on ${pipelineCameraId}`}>
                        <IconButton size="small" disabled>
                            <PlayArrowIcon />
                        </IconButton>
                    </Tooltip>
                )}

                {/* Refresh button */}
                <Tooltip title="Refresh">
                    <IconButton
                        size="small"
                        onClick={() => {
                            // Trigger a refresh via socket
                        }}
                    >
                        <RefreshIcon fontSize="small" />
                    </IconButton>
                </Tooltip>
            </CardActions>
        </Card>
    );
}
