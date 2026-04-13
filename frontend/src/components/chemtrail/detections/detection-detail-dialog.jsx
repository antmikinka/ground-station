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

import React, { useEffect, useState } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    Grid,
    Box,
    Typography,
    Chip,
    Divider,
    Table,
    TableBody,
    TableCell,
    TableRow,
    LinearProgress,
    Card,
    CardMedia,
    Skeleton,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import FlightIcon from '@mui/icons-material/Flight';
import RadarIcon from '@mui/icons-material/Radar';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import StraightenIcon from '@mui/icons-material/Straighten';
import ImageNotSupportedIcon from '@mui/icons-material/ImageNotSupported';
import TimelineIcon from '@mui/icons-material/Timeline';
import RefreshIcon from '@mui/icons-material/Refresh';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';

export default function DetectionDetailDialog({ open, onClose, detection, socket }) {
    const { t } = useTranslation('chemtrail');
    const [imageData, setImageData] = useState(null);
    const [imageLoading, setImageLoading] = useState(false);
    const [flightTrack, setFlightTrack] = useState(null);
    const [flightTrackLoading, setFlightTrackLoading] = useState(false);

    // Fetch detection image when dialog opens
    useEffect(() => {
        if (!open || !detection || !socket) return;

        setImageData(null);
        setImageLoading(true);

        // Determine source: pipeline detection (video_name + chunk_index) or database detection (id)
        const requestData = {};
        if (detection.video_name && detection.chunk_index !== undefined) {
            requestData.video_name = detection.video_name;
            requestData.chunk_index = detection.chunk_index;
        } else if (detection.id) {
            requestData.id = detection.id;
        }

        if (Object.keys(requestData).length === 0) {
            setImageLoading(false);
            return;
        }

        socket.emit('get-detection-image', requestData, (response) => {
            setImageLoading(false);
            if (response?.success && response.data) {
                setImageData(`data:image/jpeg;base64,${response.data}`);
            }
        });
    }, [open, detection, socket]);

    // Fetch flight track when detection has icao24
    useEffect(() => {
        if (!open || !detection?.icao24 || !socket) return;

        setFlightTrack(null);
        setFlightTrackLoading(true);

        socket.emit('data_request', 'get-flight-track', { icao24: detection.icao24 }, (response) => {
            setFlightTrackLoading(false);
            if (response?.success && response.data) {
                setFlightTrack(response.data);
            }
        });
    }, [open, detection?.icao24, socket]);

    if (!detection) return null;

    const formatCoordinate = (value, type) => {
        if (value === null || value === undefined) return '-';
        return `${value.toFixed(4)}°${type === 'lat' ? (value >= 0 ? ' N' : ' S') : type === 'lon' ? (value >= 0 ? ' E' : ' W') : ''}`;
    };

    const getConfidenceColor = (value) => {
        if (value >= 0.8) return 'success';
        if (value >= 0.5) return 'warning';
        return 'error';
    };

    const getConfidenceLabel = (value) => {
        if (value >= 0.8) return t('detail.confidence_high');
        if (value >= 0.5) return t('detail.confidence_medium');
        return t('detail.confidence_low');
    };

    return (
        <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
            <DialogTitle>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <RadarIcon color="info" />
                    {t('detail.title')}
                    <Chip
                        label={detection.type}
                        size="small"
                        color={detection.type === 'contrail' ? 'info' : 'default'}
                        sx={{ ml: 1 }}
                    />
                </Box>
            </DialogTitle>
            <DialogContent dividers>
                {/* Detection Image */}
                <Box sx={{ mb: 3 }}>
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                        <RadarIcon sx={{ fontSize: 16, verticalAlign: 'middle', mr: 0.5 }} />
                        {t('detail.section_image')}
                    </Typography>
                    {imageLoading ? (
                        <Skeleton variant="rectangular" width="100%" height={300} sx={{ borderRadius: 1 }} />
                    ) : imageData ? (
                        <Card sx={{ overflow: 'hidden' }}>
                            <CardMedia
                                component="img"
                                image={imageData}
                                alt="Detection overlay"
                                sx={{ maxHeight: 400, objectFit: 'contain', bgcolor: '#000' }}
                            />
                            <Box sx={{ p: 1, bgcolor: 'action.hover', display: 'flex', gap: 1, alignItems: 'center', fontSize: '0.75rem' }}>
                                <Chip label="GREEN=contrail" size="small" sx={{ height: 20, fontSize: '0.65rem', bgcolor: '#1b5e20', color: '#a5d6a7' }} />
                                <Chip label="RED=endpoints" size="small" sx={{ height: 20, fontSize: '0.65rem', bgcolor: '#b71c1c', color: '#ef9a9a' }} />
                                {detection.video_name && (
                                    <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                                        {detection.video_name} • chunk {detection.chunk_index}
                                    </Typography>
                                )}
                            </Box>
                        </Card>
                    ) : (
                        <Box sx={{ p: 3, textAlign: 'center', bgcolor: 'action.hover', borderRadius: 1 }}>
                            <ImageNotSupportedIcon sx={{ fontSize: 48, color: 'text.disabled' }} />
                            <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
                                {t('detail.no_image')}
                            </Typography>
                        </Box>
                    )}
                </Box>

                {/* Detection Metadata */}
                <Box sx={{ mb: 3 }}>
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                        {t('detail.section_detection')}
                    </Typography>
                    <Grid container spacing={2}>
                        <Grid item xs={6}>
                            <Box sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
                                <Typography variant="caption" color="text.secondary">
                                    {t('detail.timestamp')}
                                </Typography>
                                <Typography variant="body1" fontFamily="monospace">
                                    {detection.timestamp ? new Date(detection.timestamp).toLocaleString() : '-'}
                                </Typography>
                            </Box>
                        </Grid>
                        <Grid item xs={6}>
                            <Box sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
                                <Typography variant="caption" color="text.secondary">
                                    {t('detail.camera')}
                                </Typography>
                                <Typography variant="body1">
                                    {detection.camera_name || '-'}
                                </Typography>
                            </Box>
                        </Grid>
                        <Grid item xs={6}>
                            <Box sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
                                <Typography variant="caption" color="text.secondary">
                                    {t('detail.azimuth')}
                                </Typography>
                                <Typography variant="body1" fontFamily="monospace">
                                    {detection.azimuth !== null ? `${detection.azimuth.toFixed(2)}°` : '-'}
                                </Typography>
                            </Box>
                        </Grid>
                        <Grid item xs={6}>
                            <Box sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
                                <Typography variant="caption" color="text.secondary">
                                    {t('detail.elevation')}
                                </Typography>
                                <Typography variant="body1" fontFamily="monospace">
                                    {detection.elevation !== null ? `${detection.elevation.toFixed(2)}°` : '-'}
                                </Typography>
                            </Box>
                        </Grid>
                    </Grid>
                </Box>

                {/* Estimated Position */}
                <Box sx={{ mb: 3 }}>
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                        <LocationOnIcon sx={{ fontSize: 16, verticalAlign: 'middle', mr: 0.5 }} />
                        {t('detail.section_position')}
                    </Typography>
                    <Grid container spacing={2}>
                        <Grid item xs={6}>
                            <Box sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
                                <Typography variant="caption" color="text.secondary">
                                    {t('detail.latitude')}
                                </Typography>
                                <Typography variant="body1" fontFamily="monospace">
                                    {formatCoordinate(detection.estimated_lat, 'lat')}
                                </Typography>
                            </Box>
                        </Grid>
                        <Grid item xs={6}>
                            <Box sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
                                <Typography variant="caption" color="text.secondary">
                                    {t('detail.longitude')}
                                </Typography>
                                <Typography variant="body1" fontFamily="monospace">
                                    {formatCoordinate(detection.estimated_lon, 'lon')}
                                </Typography>
                            </Box>
                        </Grid>
                        <Grid item xs={12}>
                            <Box sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
                                <Typography variant="caption" color="text.secondary">
                                    <StraightenIcon sx={{ fontSize: 16, verticalAlign: 'middle', mr: 0.5 }} />
                                    {t('detail.estimated_altitude')}
                                </Typography>
                                <Typography variant="body1" fontFamily="monospace">
                                    {detection.estimated_alt !== null ? `${detection.estimated_alt.toFixed(0)} m / ${(detection.estimated_alt * 3.28084).toFixed(0)} ft` : '-'}
                                </Typography>
                            </Box>
                        </Grid>
                    </Grid>
                </Box>

                {/* Flight Correlation */}
                <Box sx={{ mb: 3 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                        <Typography variant="subtitle2" color="text.secondary">
                            <FlightIcon sx={{ fontSize: 16, verticalAlign: 'middle', mr: 0.5 }} />
                            {t('detail.section_flight')}
                        </Typography>
                        {detection.icao24 && (
                            <Tooltip title={t('detail.refresh_flight_track')}>
                                <IconButton
                                    size="small"
                                    disabled={flightTrackLoading}
                                    onClick={() => {
                                        setFlightTrack(null);
                                        setFlightTrackLoading(true);
                                        socket.emit('data_request', 'get-flight-track', { icao24: detection.icao24 }, (response) => {
                                            setFlightTrackLoading(false);
                                            if (response?.success && response.data) {
                                                setFlightTrack(response.data);
                                            }
                                        });
                                    }}
                                >
                                    <RefreshIcon fontSize="small" />
                                </IconButton>
                            </Tooltip>
                        )}
                    </Box>
                    {(detection.icao24 || detection.callsign) ? (
                        <>
                            <Table size="small">
                                <TableBody>
                                    <TableRow>
                                        <TableCell>{t('detail.icao24')}</TableCell>
                                        <TableCell>
                                            <Typography variant="body2" fontFamily="monospace">
                                                {detection.icao24 || '-'}
                                            </Typography>
                                        </TableCell>
                                    </TableRow>
                                    <TableRow>
                                        <TableCell>{t('detail.callsign')}</TableCell>
                                        <TableCell>
                                            <Typography variant="body2" fontFamily="monospace">
                                                {detection.callsign || '-'}
                                            </Typography>
                                        </TableCell>
                                    </TableRow>
                                    {detection.origin && (
                                        <TableRow>
                                            <TableCell>{t('detail.origin')}</TableCell>
                                            <TableCell>{detection.origin}</TableCell>
                                        </TableRow>
                                    )}
                                    {detection.destination && (
                                        <TableRow>
                                            <TableCell>{t('detail.destination')}</TableCell>
                                            <TableCell>{detection.destination}</TableCell>
                                        </TableRow>
                                    )}
                                    {detection.aircraft_type && (
                                        <TableRow>
                                            <TableCell>{t('detail.aircraft_type')}</TableCell>
                                            <TableCell>{detection.aircraft_type}</TableCell>
                                        </TableRow>
                                    )}
                                </TableBody>
                            </Table>

                            {/* Flight Track */}
                            {flightTrackLoading && (
                                <Box sx={{ mt: 2 }}>
                                    <Skeleton variant="rectangular" height={120} sx={{ borderRadius: 1 }} />
                                </Box>
                            )}
                            {flightTrack && (
                                <Box sx={{ mt: 2 }}>
                                    <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1 }}>
                                        <TimelineIcon sx={{ fontSize: 14 }} />
                                        {t('detail.flight_track_positions')}
                                        {flightTrack.tracks && (
                                            <Chip
                                                label={`${Array.isArray(flightTrack.tracks) ? flightTrack.tracks.length : 0} pts`}
                                                size="small"
                                                sx={{ height: 18, fontSize: '0.65rem', ml: 1 }}
                                            />
                                        )}
                                    </Typography>
                                    <Box
                                        sx={{
                                            maxHeight: 180,
                                            overflow: 'auto',
                                            bgcolor: 'action.hover',
                                            borderRadius: 1,
                                            p: 1,
                                        }}
                                    >
                                        {Array.isArray(flightTrack.tracks) && flightTrack.tracks.length > 0 ? (
                                            flightTrack.tracks.slice(-10).map((position, index) => (
                                                <Box
                                                    key={index}
                                                    sx={{
                                                        display: 'flex',
                                                        justifyContent: 'space-between',
                                                        alignItems: 'center',
                                                        py: 0.5,
                                                        borderBottom: index < Math.min(flightTrack.tracks.length, 10) - 1 ? '1px solid' : 'none',
                                                        borderColor: 'divider',
                                                    }}
                                                >
                                                    <Typography variant="caption" fontFamily="monospace">
                                                        {position.timestamp ? new Date(position.timestamp).toLocaleTimeString() : '-'}
                                                    </Typography>
                                                    <Typography variant="caption">
                                                        {position.lat?.toFixed(4)}, {position.lon?.toFixed(4)}
                                                    </Typography>
                                                    <Typography variant="caption">
                                                        {position.altitude != null ? `${Math.round(position.altitude)}m / ${Math.round(position.altitude * 3.28084)}ft` : '-'}
                                                    </Typography>
                                                </Box>
                                            ))
                                        ) : (
                                            <Typography variant="caption" color="text.disabled" fontStyle="italic">
                                                {t('detail.no_flight_track')}
                                            </Typography>
                                        )}
                                    </Box>
                                </Box>
                            )}
                        </>
                    ) : (
                        <Typography variant="body2" color="text.disabled" fontStyle="italic">
                            {t('detail.no_flight_correlation')}
                        </Typography>
                    )}
                </Box>

                {/* Confidence Score */}
                <Box>
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                        {t('detail.section_confidence')}
                    </Typography>
                    <Box sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 1 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                            <Typography variant="body2">{t('detail.detection_confidence')}</Typography>
                            <Chip
                                label={getConfidenceLabel(detection.confidence)}
                                size="small"
                                color={getConfidenceColor(detection.confidence)}
                            />
                        </Box>
                        <LinearProgress
                            variant="determinate"
                            value={Math.round(detection.confidence * 100)}
                            color={getConfidenceColor(detection.confidence)}
                            sx={{ height: 8, borderRadius: 1 }}
                        />
                        <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                            {Math.round(detection.confidence * 100)}%
                        </Typography>
                    </Box>
                    {detection.correlation_score !== null && detection.correlation_score !== undefined && (
                        <Box sx={{ p: 2, bgcolor: 'action.hover', borderRadius: 1, mt: 1 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                                <Typography variant="body2">{t('detail.correlation_confidence')}</Typography>
                                <Chip
                                    label={Math.round(detection.correlation_score * 100)}
                                    size="small"
                                    color={detection.correlation_score > 0.7 ? 'success' : 'default'}
                                />
                            </Box>
                            <LinearProgress
                                variant="determinate"
                                value={Math.round(detection.correlation_score * 100)}
                                color={detection.correlation_score > 0.7 ? 'success' : 'default'}
                                sx={{ height: 8, borderRadius: 1 }}
                            />
                            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                                {Math.round(detection.correlation_score * 100)}%
                            </Typography>
                        </Box>
                    )}
                </Box>

                {/* FR24 Enrichment */}
                {detection.fr24_enrichment && (
                    <Box sx={{ mt: 3 }}>
                        <Divider sx={{ my: 2 }} />
                        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                            {t('detail.fr24_enrichment')}
                        </Typography>
                        <Typography variant="body2" fontFamily="monospace" sx={{ whiteSpace: 'pre-wrap' }}>
                            {JSON.stringify(detection.fr24_enrichment, null, 2)}
                        </Typography>
                    </Box>
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose} variant="outlined">
                    {t('actions.close')}
                </Button>
            </DialogActions>
        </Dialog>
    );
}
