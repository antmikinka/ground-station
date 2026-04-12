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
    Box,
    Paper,
    Typography,
    Chip,
    Grid,
    Divider,
    IconButton,
    Table,
    TableBody,
    TableCell,
    TableRow,
    Tooltip,
    Collapse,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import CloseIcon from '@mui/icons-material/Close';
import FlightIcon from '@mui/icons-material/Flight';
import AirplanemodeActiveIcon from '@mui/icons-material/AirplanemodeActive';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import MapIcon from '@mui/icons-material/Map';
import TimelineIcon from '@mui/icons-material/Timeline';

export default function FlightDetailPanel({ flight, onClose }) {
    const { t } = useTranslation('chemtrail');

    if (!flight) return null;

    const formatTimestamp = (isoString) => {
        if (!isoString) return '-';
        return new Date(isoString).toLocaleString();
    };

    return (
        <Paper
            elevation={3}
            sx={{
                mt: 2,
                p: 2,
                bgcolor: 'background.paper',
                position: 'relative',
            }}
        >
            {/* Close Button */}
            <IconButton
                size="small"
                onClick={onClose}
                sx={{ position: 'absolute', top: 8, right: 8 }}
            >
                <CloseIcon />
            </IconButton>

            {/* Header */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <FlightIcon color="primary" />
                <Typography variant="h6">
                    {flight.callsign || flight.icao24}
                </Typography>
                {flight.registration && (
                    <Chip
                        label={flight.registration}
                        size="small"
                        variant="outlined"
                        sx={{ ml: 1 }}
                    />
                )}
            </Box>

            {/* Flight Info Grid */}
            <Grid container spacing={2}>
                {/* Basic Info */}
                <Grid item xs={12} md={6}>
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                        <AirplanemodeActiveIcon sx={{ fontSize: 16, verticalAlign: 'middle', mr: 0.5 }} />
                        {t('flights.detail.basic_info')}
                    </Typography>
                    <Table size="small">
                        <TableBody>
                            <TableRow>
                                <TableCell sx={{ fontWeight: 600 }}>{t('flights.detail.icao24')}</TableCell>
                                <TableCell>
                                    <Typography variant="body2" fontFamily="monospace">
                                        {flight.icao24 || '-'}
                                    </Typography>
                                </TableCell>
                            </TableRow>
                            <TableRow>
                                <TableCell sx={{ fontWeight: 600 }}>{t('flights.detail.callsign')}</TableCell>
                                <TableCell>
                                    <Typography variant="body2">
                                        {flight.callsign || '-'}
                                    </Typography>
                                </TableCell>
                            </TableRow>
                            <TableRow>
                                <TableCell sx={{ fontWeight: 600 }}>{t('flights.detail.registration')}</TableCell>
                                <TableCell>
                                    <Typography variant="body2" fontFamily="monospace">
                                        {flight.registration || '-'}
                                    </Typography>
                                </TableCell>
                            </TableRow>
                            <TableRow>
                                <TableCell sx={{ fontWeight: 600 }}>{t('flights.detail.aircraft_type')}</TableCell>
                                <TableCell>
                                    <Typography variant="body2">
                                        {flight.aircraft_type || '-'}
                                    </Typography>
                                </TableCell>
                            </TableRow>
                        </TableBody>
                    </Table>
                </Grid>

                {/* Route Info */}
                <Grid item xs={12} md={6}>
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                        <LocationOnIcon sx={{ fontSize: 16, verticalAlign: 'middle', mr: 0.5 }} />
                        {t('flights.detail.route_info')}
                    </Typography>
                    <Table size="small">
                        <TableBody>
                            <TableRow>
                                <TableCell sx={{ fontWeight: 600 }}>{t('flights.detail.origin')}</TableCell>
                                <TableCell>
                                    <Typography variant="body2">
                                        {flight.origin || '-'}
                                    </Typography>
                                </TableCell>
                            </TableRow>
                            <TableRow>
                                <TableCell sx={{ fontWeight: 600 }}>{t('flights.detail.destination')}</TableCell>
                                <TableCell>
                                    <Typography variant="body2">
                                        {flight.destination || '-'}
                                    </Typography>
                                </TableCell>
                            </TableRow>
                            {flight.first_seen && (
                                <TableRow>
                                    <TableCell sx={{ fontWeight: 600 }}>{t('flights.detail.first_seen')}</TableCell>
                                    <TableCell>
                                        <Typography variant="body2" fontFamily="monospace">
                                            {formatTimestamp(flight.first_seen)}
                                        </Typography>
                                    </TableCell>
                                </TableRow>
                            )}
                            {flight.last_seen && (
                                <TableRow>
                                    <TableCell sx={{ fontWeight: 600 }}>{t('flights.detail.last_seen')}</TableCell>
                                    <TableCell>
                                        <Typography variant="body2" fontFamily="monospace">
                                            {formatTimestamp(flight.last_seen)}
                                        </Typography>
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </Grid>

                {/* Data Sources */}
                <Grid item xs={12}>
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                        <MapIcon sx={{ fontSize: 16, verticalAlign: 'middle', mr: 0.5 }} />
                        {t('flights.detail.data_sources')}
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                        {flight.data_sources?.includes('opensky') && (
                            <Chip
                                label="OpenSky Network"
                                size="small"
                                color="primary"
                                variant="outlined"
                            />
                        )}
                        {flight.data_sources?.includes('fr24') && (
                            <Chip
                                label="FlightRadar24"
                                size="small"
                                color="secondary"
                                variant="outlined"
                            />
                        )}
                        {flight.data_sources?.includes('adsb') && (
                            <Chip
                                label="ADS-B"
                                size="small"
                                variant="outlined"
                            />
                        )}
                        {!flight.data_sources?.length && (
                            <Typography variant="body2" color="text.disabled">
                                {t('flights.detail.no_data_sources')}
                            </Typography>
                        )}
                    </Box>
                </Grid>

                {/* Flight Track */}
                {flight.track && flight.track.length > 0 && (
                    <Grid item xs={12}>
                        <Divider sx={{ my: 1 }} />
                        <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                            <TimelineIcon sx={{ fontSize: 16, verticalAlign: 'middle', mr: 0.5 }} />
                            {t('flights.detail.flight_track')}
                        </Typography>
                        <Box
                            sx={{
                                maxHeight: 200,
                                overflow: 'auto',
                                bgcolor: 'action.hover',
                                borderRadius: 1,
                                p: 1,
                            }}
                        >
                            {flight.track.slice(-10).map((position, index) => (
                                <Box
                                    key={index}
                                    sx={{
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        py: 0.5,
                                        borderBottom: index < flight.track.length - 1 ? '1px solid' : 'none',
                                        borderColor: 'divider',
                                    }}
                                >
                                    <Typography variant="caption" fontFamily="monospace">
                                        {formatTimestamp(position.timestamp)}
                                    </Typography>
                                    <Typography variant="caption">
                                        {position.lat?.toFixed(4)}, {position.lon?.toFixed(4)}
                                    </Typography>
                                    <Typography variant="caption">
                                        {position.altitude !== null ? `${position.altitude}m` : '-'}
                                    </Typography>
                                </Box>
                            ))}
                        </Box>
                    </Grid>
                )}
            </Grid>
        </Paper>
    );
}
