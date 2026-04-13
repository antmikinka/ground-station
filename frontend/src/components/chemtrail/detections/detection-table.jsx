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
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    TextField,
    Alert,
    AlertTitle,
    Chip,
    IconButton,
    Tooltip,
    Typography,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import VisibilityIcon from '@mui/icons-material/Visibility';
import DeleteIcon from '@mui/icons-material/Delete';
import FilterListIcon from '@mui/icons-material/FilterList';
import { useTranslation } from 'react-i18next';
import { useSocket } from '../../common/socket.jsx';
import { useDispatch, useSelector } from 'react-redux';
import {
    fetchDetections,
    deleteDetection,
    setSelectedDetection,
    setFilters,
    resetFilters,
    clearSelectedDetection,
} from './detections-slice.js';
import { toast } from '../../../utils/toast-with-timestamp.jsx';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import DetectionDetailDialog from './detection-detail-dialog.jsx';

export default function DetectionTable() {
    const { socket } = useSocket();
    const dispatch = useDispatch();
    const { t } = useTranslation('chemtrail');
    const [selected, setSelected] = useState([]);
    const [pageSize, setPageSize] = useState(25);
    const [openDetailDialog, setOpenDetailDialog] = useState(false);
    const [openDeleteConfirm, setOpenDeleteConfirm] = useState(false);

    const {
        loading,
        detections,
        status,
        error,
        filters,
        pagination,
        selectedDetection,
    } = useSelector((state) => state.chemtrailDetections);

    const columns = useMemo(() => [
        {
            field: 'timestamp',
            headerName: t('detections.table.timestamp'),
            flex: 1,
            minWidth: 160,
            valueFormatter: (params) => {
                if (!params.value) return '-';
                return new Date(params.value).toLocaleString();
            },
            sortComparator: (v1, v2) => {
                return new Date(v1) - new Date(v2);
            },
        },
        {
            field: 'camera_name',
            headerName: t('detections.table.camera'),
            flex: 1,
            minWidth: 120,
        },
        {
            field: 'icao24',
            headerName: t('detections.table.icao24'),
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
            headerName: t('detections.table.callsign'),
            flex: 1,
            minWidth: 100,
        },
        {
            field: 'type',
            headerName: t('detections.table.type'),
            flex: 0.8,
            minWidth: 100,
            renderCell: (params) => (
                <Chip
                    label={params.value}
                    size="small"
                    color={params.value === 'contrail' ? 'info' : 'default'}
                />
            ),
        },
        {
            field: 'confidence',
            headerName: t('detections.table.confidence'),
            flex: 0.8,
            minWidth: 90,
            renderCell: (params) => (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Box
                        sx={{
                            flex: 1,
                            height: 6,
                            bgcolor: 'action.hover',
                            borderRadius: '3px',
                            overflow: 'hidden',
                        }}
                    >
                        <Box
                            sx={{
                                height: '100%',
                                width: `${Math.round(params.value * 100)}%`,
                                bgcolor: params.value > 0.7 ? 'success.main' : params.value > 0.4 ? 'warning.main' : 'error.main',
                            }}
                        />
                    </Box>
                    <Typography variant="body2" sx={{ minWidth: 40 }}>
                        {Math.round(params.value * 100)}%
                    </Typography>
                </Box>
            ),
        },
        {
            field: 'correlation_score',
            headerName: t('detections.table.correlation_score'),
            flex: 0.8,
            minWidth: 90,
            renderCell: (params) => (
                params.value ? (
                    <Chip
                        label={Math.round(params.value * 100)}
                        size="small"
                        color={params.value > 0.7 ? 'success' : 'default'}
                    />
                ) : (
                    <Typography variant="body2" color="text.disabled">-</Typography>
                )
            ),
        },
    ], [t]);

    const handleRefresh = () => {
        dispatch(fetchDetections({
            socket,
            params: {
                camera: filters.camera !== 'all' ? filters.camera : undefined,
                dateFrom: filters.dateFrom || undefined,
                dateTo: filters.dateTo || undefined,
                type: filters.type !== 'all' ? filters.type : undefined,
            },
        }));
    };

    const handleRowClick = (params) => {
        dispatch(setSelectedDetection(params.row));
        setOpenDetailDialog(true);
    };

    const handleDelete = () => {
        dispatch(deleteDetection({ socket, id: selected[0] }))
            .unwrap()
            .then(() => {
                toast.success(t('detection.deleted_success'));
                setOpenDeleteConfirm(false);
                handleRefresh();
            })
            .catch((err) => {
                toast.error(err.message);
            });
    };

    const handleFilterChange = (field, value) => {
        dispatch(setFilters({ [field]: value }));
    };

    // Auto-refresh on mount
    useEffect(() => {
        handleRefresh();
    }, []);

    return (
        <Paper elevation={3} sx={{ padding: 2, marginTop: 0 }}>
            <Alert severity="info" sx={{ mb: 2 }}>
                <AlertTitle>{t('detections.title')}</AlertTitle>
                {t('detections.subtitle')}
            </Alert>

            {/* Filters */}
            <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
                <FormControl size="small" sx={{ minWidth: 150 }}>
                    <InputLabel>{t('detections.filters.camera')}</InputLabel>
                    <Select
                        value={filters.camera}
                        label={t('detections.filters.camera')}
                        onChange={(e) => handleFilterChange('camera', e.target.value)}
                    >
                        <MenuItem value="all">{t('detections.filters.all_cameras')}</MenuItem>
                        {/* Camera options would be populated from cameras state */}
                    </Select>
                </FormControl>

                <FormControl size="small" sx={{ minWidth: 150 }}>
                    <InputLabel>{t('detections.filters.type')}</InputLabel>
                    <Select
                        value={filters.type}
                        label={t('detections.filters.type')}
                        onChange={(e) => handleFilterChange('type', e.target.value)}
                    >
                        <MenuItem value="all">{t('detections.filters.all_types')}</MenuItem>
                        <MenuItem value="contrail">{t('detections.filters.contrail')}</MenuItem>
                        <MenuItem value="cloud">{t('detections.filters.cloud')}</MenuItem>
                        <MenuItem value="other">{t('detections.filters.other')}</MenuItem>
                    </Select>
                </FormControl>

                <TextField
                    size="small"
                    type="date"
                    label={t('detections.filters.date_from')}
                    value={filters.dateFrom}
                    onChange={(e) => handleFilterChange('dateFrom', e.target.value)}
                    sx={{ minWidth: 150 }}
                    InputLabelProps={{ shrink: true }}
                />

                <TextField
                    size="small"
                    type="date"
                    label={t('detections.filters.date_to')}
                    value={filters.dateTo}
                    onChange={(e) => handleFilterChange('dateTo', e.target.value)}
                    sx={{ minWidth: 150 }}
                    InputLabelProps={{ shrink: true }}
                />

                <Stack direction="row" spacing={1} sx={{ ml: 'auto' }}>
                    <Button
                        variant="outlined"
                        startIcon={<FilterListIcon />}
                        onClick={() => dispatch(resetFilters())}
                    >
                        {t('detections.filters.reset')}
                    </Button>
                    <Button
                        variant="contained"
                        startIcon={<RefreshIcon />}
                        onClick={handleRefresh}
                        disabled={loading}
                    >
                        {t('detections.actions.refresh')}
                    </Button>
                </Stack>
            </Box>

            {/* Data Grid */}
            <Box sx={{ width: '100%', height: 600 }}>
                <DataGrid
                    loading={loading}
                    rows={detections}
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
                            sortModel: [{ field: 'timestamp', sort: 'desc' }],
                        },
                    }}
                    pageSizeOptions={[10, 25, 50, 100]}
                    onPageSizeChange={(newPageSize) => setPageSize(newPageSize)}
                    getRowId={(row) => row.id}
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
            <Stack direction="row" spacing={2} sx={{ mt: 2 }}>
                <Button
                    variant="contained"
                    disabled={selected.length !== 1}
                    onClick={() => {
                        const selectedRow = detections.find(row => row.id === selected[0]);
                        if (selectedRow) {
                            dispatch(setSelectedDetection(selectedRow));
                            setOpenDetailDialog(true);
                        }
                    }}
                    startIcon={<VisibilityIcon />}
                >
                    {t('detections.actions.view_details')}
                </Button>
                <Button
                    variant="contained"
                    disabled={selected.length < 1}
                    color="error"
                    onClick={() => setOpenDeleteConfirm(true)}
                    startIcon={<DeleteIcon />}
                >
                    {t('detections.actions.delete')}
                </Button>
            </Stack>

            {/* Detail Dialog */}
            <DetectionDetailDialog
                open={openDetailDialog}
                onClose={() => {
                    setOpenDetailDialog(false);
                    dispatch(clearSelectedDetection());
                }}
                detection={selectedDetection}
                socket={socket}
            />

            {/* Delete Confirmation Dialog */}
            <Dialog
                open={openDeleteConfirm}
                onClose={() => setOpenDeleteConfirm(false)}
            >
                <DialogTitle>{t('detection.confirm_deletion')}</DialogTitle>
                <DialogContent>
                    {t('detection.confirm_delete_message')}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setOpenDeleteConfirm(false)} color="error" variant="outlined">
                        {t('actions.cancel')}
                    </Button>
                    <Button onClick={handleDelete} color="error" variant="contained">
                        {t('detections.actions.delete')}
                    </Button>
                </DialogActions>
            </Dialog>
        </Paper>
    );
}
