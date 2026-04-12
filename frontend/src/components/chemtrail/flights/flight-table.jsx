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

import * as React from 'react';
import { useState, useMemo, useEffect } from 'react';
import { DataGrid, gridClasses } from '@mui/x-data-grid';
import {
    Box,
    Paper,
    Stack,
    Button,
    Alert,
    AlertTitle,
    Chip,
    Tooltip,
    Typography,
    IconButton,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import VisibilityIcon from '@mui/icons-material/Visibility';
import TrackChangesIcon from '@mui/icons-material/TrackChanges';
import { useTranslation } from 'react-i18next';
import { useSocket } from '../../common/socket.jsx';
import { useDispatch, useSelector } from 'react-redux';
import {
    fetchLiveFlights,
    setSelectedFlight,
    fetchFlightTrack,
    clearSelectedFlight,
    setLastUpdated,
} from './flights-slice.js';
import FlightDetailPanel from './flight-detail-panel.jsx';

export default function FlightTable() {
    const { socket } = useSocket();
    const dispatch = useDispatch();
    const { t } = useTranslation('chemtrail');
    const [selected, setSelected] = useState([]);
    const [pageSize, setPageSize] = useState(25);
    const [showDetailPanel, setShowDetailPanel] = useState(false);

    const {
        loading,
        flights,
        status,
        error,
        selectedFlight,
        lastUpdated,
    } = useSelector((state) => state.chemtrailFlights);

    const columns = useMemo(() => [
        {
            field: 'icao24',
            headerName: t('flights.table.icao24'),
            flex: 1,
            minWidth: 100,
            renderCell: (params) => (
                <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                    {params.value || '-'}
                </Typography>
            ),
        },
        {
            field: 'callsign',
            headerName: t('flights.table.callsign'),
            flex: 1,
            minWidth: 120,
            renderCell: (params) => (
                params.value ? (
                    <Typography variant="body2" fontWeight={600}>
                        {params.value}
                    </Typography>
                ) : (
                    <Typography variant="body2" color="text.disabled">-</Typography>
                )
            ),
        },
        {
            field: 'registration',
            headerName: t('flights.table.registration'),
            flex: 0.8,
            minWidth: 100,
        },
        {
            field: 'aircraft_type',
            headerName: t('flights.table.aircraft_type'),
            flex: 0.8,
            minWidth: 100,
            renderCell: (params) => (
                params.value ? (
                    <Chip label={params.value} size="small" variant="outlined" />
                ) : (
                    <Typography variant="body2" color="text.disabled">-</Typography>
                )
            ),
        },
        {
            field: 'origin',
            headerName: t('flights.table.origin'),
            flex: 0.8,
            minWidth: 80,
        },
        {
            field: 'destination',
            headerName: t('flights.table.destination'),
            flex: 0.8,
            minWidth: 80,
        },
        {
            field: 'data_sources',
            headerName: t('flights.table.data_sources'),
            flex: 1,
            minWidth: 150,
            renderCell: (params) => (
                <Box sx={{ display: 'flex', gap: 0.5 }}>
                    {params.value?.includes('opensky') && (
                        <Tooltip title="OpenSky Network">
                            <Chip
                                label="OpenSky"
                                size="small"
                                color="primary"
                                variant="outlined"
                            />
                        </Tooltip>
                    )}
                    {params.value?.includes('fr24') && (
                        <Tooltip title="FlightRadar24">
                            <Chip
                                label="FR24"
                                size="small"
                                color="secondary"
                                variant="outlined"
                            />
                        </Tooltip>
                    )}
                    {params.value?.includes('adsb') && (
                        <Tooltip title="ADS-B">
                            <Chip
                                label="ADS-B"
                                size="small"
                                variant="outlined"
                            />
                        </Tooltip>
                    )}
                </Box>
            ),
        },
    ], [t]);

    const handleRefresh = () => {
        dispatch(fetchLiveFlights({ socket }))
            .unwrap()
            .then(() => {
                dispatch(setLastUpdated(new Date().toISOString()));
            });
    };

    const handleRowClick = (params) => {
        dispatch(setSelectedFlight(params.row));
        setShowDetailPanel(true);
        // Fetch flight track when row is clicked
        const now = new Date();
        const oneHourAgo = new Date(now.getTime() - 60 * 60 * 1000);
        dispatch(fetchFlightTrack({
            socket,
            icao24: params.row.icao24,
            startTime: oneHourAgo.toISOString(),
            endTime: now.toISOString(),
        }));
    };

    const handleCloseDetail = () => {
        setShowDetailPanel(false);
        dispatch(clearSelectedFlight());
    };

    // Auto-refresh on mount and every 30 seconds
    useEffect(() => {
        handleRefresh();
        const interval = setInterval(handleRefresh, 30000);
        return () => clearInterval(interval);
    }, []);

    return (
        <Paper elevation={3} sx={{ padding: 2, marginTop: 0 }}>
            <Alert severity="info" sx={{ mb: 2 }}>
                <AlertTitle>{t('flights.title')}</AlertTitle>
                {t('flights.subtitle')}
                {lastUpdated && (
                    <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                        {t('flights.last_updated')}: {new Date(lastUpdated).toLocaleTimeString()}
                    </Typography>
                )}
            </Alert>

            {/* Data Grid */}
            <Box sx={{ width: '100%', height: 600 }}>
                <DataGrid
                    loading={loading}
                    rows={flights}
                    columns={columns}
                    checkboxSelection
                    disableRowSelectionOnClick
                    onRowSelectionModelChange={(selectedRows) => {
                        setSelected(selectedRows);
                    }}
                    onRowClick={handleRowClick}
                    initialState={{
                        pagination: { paginationModel: { pageSize: 25 } },
                        sorting: {
                            sortModel: [{ field: 'callsign', sort: 'asc' }],
                        },
                    }}
                    pageSizeOptions={[10, 25, 50, 100]}
                    onPageSizeChange={(newPageSize) => setPageSize(newPageSize)}
                    getRowId={(row) => row.icao24}
                    sx={{
                        border: 0,
                        [`& .${gridClasses.cell}:focus, & .${gridClasses.cell}:focus-within`]: {
                            outline: 'none',
                        },
                        [`& .${gridClasses.columnHeader}:focus, & .${gridClasses.columnHeader}:focus-within`]: {
                            outline: 'none',
                        },
                    }}
                />
            </Box>

            {/* Action Buttons */}
            <Stack direction="row" spacing={2} sx={{ mt: 2, alignItems: 'center' }}>
                <Button
                    variant="contained"
                    disabled={selected.length !== 1}
                    onClick={() => {
                        const selectedRow = flights.find(row => row.icao24 === selected[0]);
                        if (selectedRow) {
                            dispatch(setSelectedFlight(selectedRow));
                            setShowDetailPanel(true);
                        }
                    }}
                    startIcon={<VisibilityIcon />}
                >
                    {t('flights.actions.view_details')}
                </Button>
                <Button
                    variant="outlined"
                    startIcon={<TrackChangesIcon />}
                    onClick={handleRefresh}
                    disabled={loading}
                >
                    {t('flights.actions.refresh')}
                </Button>
                <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
                    {flights.length} {t('flights.actions.aircraft')}
                </Typography>
            </Stack>

            {/* Detail Panel */}
            {showDetailPanel && selectedFlight && (
                <FlightDetailPanel
                    flight={selectedFlight}
                    onClose={handleCloseDetail}
                />
            )}
        </Paper>
    );
}
