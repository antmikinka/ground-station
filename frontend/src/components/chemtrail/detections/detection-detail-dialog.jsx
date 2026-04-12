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

import React from 'react';
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
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import FlightIcon from '@mui/icons-material/Flight';
import RadarIcon from '@mui/icons-material/Radar';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import StraightenIcon from '@mui/icons-material/Straighten';

export default function DetectionDetailDialog({ open, onClose, detection }) {
    const { t } = useTranslation('chemtrail');

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
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                        <FlightIcon sx={{ fontSize: 16, verticalAlign: 'middle', mr: 0.5 }} />
                        {t('detail.section_flight')}
                    </Typography>
                    {(detection.icao24 || detection.callsign) ? (
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
