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

import React, { useEffect, useState, useCallback } from 'react';
import {
    Box,
    Paper,
    Grid,
    Card,
    CardContent,
    Typography,
    Chip,
    CircularProgress,
    LinearProgress,
    Alert,
    AlertTitle,
    Stack,
    Divider,
    Tooltip,
    Button,
    IconButton,
    TextField,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogContentText,
    DialogActions,
    Tabs,
    Tab,
    FormControlLabel,
    Switch,
    MenuItem,
    Select,
    InputLabel,
    FormControl,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Collapse,
} from '@mui/material';
import { DataGrid } from '@mui/x-data-grid';
import { useTranslation } from 'react-i18next';
import { useSocket } from '../../common/socket.jsx';
import { useDispatch, useSelector } from 'react-redux';
import {
    fetchPipelineStatus,
    fetchPipelineStats,
    fetchPipelineConfig,
    updatePipelineConfig,
    startLivePipeline,
    stopLivePipeline,
    submitLocalJob,
    submitYoutubeJob,
    cancelPipelineJob,
    fetchVideoCatalog,
    startHistoricalScan,
    fetchWebcamSources,
    setPipelineRunning,
    setLivePipelineCameraId,
    updateJob,
} from './pipeline-slice.js';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import RefreshIcon from '@mui/icons-material/Refresh';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import YouTubeIcon from '@mui/icons-material/YouTube';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import SettingsIcon from '@mui/icons-material/Settings';
import VideocamIcon from '@mui/icons-material/Videocam';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import WarningIcon from '@mui/icons-material/Warning';
import PendingIcon from '@mui/icons-material/Pending';
import CancelIcon from '@mui/icons-material/Cancel';
import CancelOutlinedIcon from '@mui/icons-material/CancelOutlined';
import SpeedIcon from '@mui/icons-material/Speed';
import StorageIcon from '@mui/icons-material/Storage';
import RadarIcon from '@mui/icons-material/Radar';

// ==================== Tab Panel ====================

function TabPanel({ children, value, index, ...other }) {
    return (
        <div
            role="tabpanel"
            hidden={value !== index}
            id={`pipeline-tabpanel-${index}`}
            aria-labelledby={`pipeline-tab-${index}`}
            {...other}
        >
            {value === index && <Box sx={{ py: 2 }}>{children}</Box>}
        </div>
    );
}

// ==================== Status Helpers ====================

const getStatusColor = (status) => {
    switch (status) {
        case 'completed': return 'success';
        case 'running': return 'info';
        case 'pending': return 'warning';
        case 'failed': return 'error';
        case 'cancelled': return 'default';
        default: return 'default';
    }
};

const getStatusIcon = (status) => {
    switch (status) {
        case 'completed': return <CheckCircleIcon fontSize="small" />;
        case 'running': return <CircularProgress size={14} thickness={5} />;
        case 'pending': return <PendingIcon fontSize="small" />;
        case 'failed': return <ErrorIcon fontSize="small" />;
        case 'cancelled': return <CancelIcon fontSize="small" />;
        default: return <PendingIcon fontSize="small" />;
    }
};

const getStageLabel = (stage) => {
    const labels = {
        acquisition: 'Acquisition',
        sorting: 'Sorting',
        weather_enrichment: 'Weather',
        quality_scoring: 'Quality',
        chunking: 'Chunking',
        detection: 'Detection',
        archival: 'Archival',
        complete: 'Complete',
    };
    return labels[stage] || stage;
};

const formatDuration = (createdAt, completedAt) => {
    if (!createdAt) return '-';
    const start = new Date(createdAt);
    const end = completedAt ? new Date(completedAt) : new Date();
    const ms = end - start;
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ${minutes % 60}m`;
};

// ==================== Main Component ====================

export default function PipelineControl() {
    const { socket } = useSocket();
    const dispatch = useDispatch();
    const { t } = useTranslation('chemtrail');
    const [tabValue, setTabValue] = useState(0);

    const {
        jobs,
        livePipelineRunning,
        livePipelineCameraId,
        config,
        stats,
        videoCatalog,
        webcamSources,
        loading,
        error,
    } = useSelector((state) => state.chemtrailPipeline);

    // Local form states
    const [localPath, setLocalPath] = useState('');
    const [youtubeUrl, setYoutubeUrl] = useState('');
    const [selectedCameraId, setSelectedCameraId] = useState('');
    const [liveDuration, setLiveDuration] = useState(1);
    const [liveChunkInterval, setLiveChunkInterval] = useState(30);
    const [skipStill, setSkipStill] = useState(true);
    const [applyOverlay, setApplyOverlay] = useState(false);
    const [scanDirectory, setScanDirectory] = useState('');
    const [scanRecursive, setScanRecursive] = useState(true);
    const [configForm, setConfigForm] = useState({});

    // Confirmation dialog
    const [confirmDialog, setConfirmDialog] = useState({ open: false, action: '', title: '', message: '' });

    // ==================== Data Fetching ====================

    const handleRefreshAll = useCallback(() => {
        if (!socket) return;
        dispatch(fetchPipelineStatus({ socket }));
        dispatch(fetchPipelineStats({ socket }));
        dispatch(fetchPipelineConfig({ socket }));
        dispatch(fetchWebcamSources({ socket }));
    }, [socket, dispatch]);

    useEffect(() => {
        handleRefreshAll();
        const interval = setInterval(handleRefreshAll, 30000);
        return () => clearInterval(interval);
    }, [handleRefreshAll]);

    // ==================== Real-time Socket Events ====================

    useEffect(() => {
        if (!socket) return;

        socket.on('chemtrail:pipeline-started', (data) => {
            dispatch(setPipelineRunning(true));
            dispatch(setLivePipelineCameraId(data.camera_id));
        });

        socket.on('chemtrail:pipeline-stopped', () => {
            dispatch(setPipelineRunning(false));
            dispatch(setLivePipelineCameraId(null));
        });

        socket.on('chemtrail:job-submitted', (data) => {
            dispatch(updateJob({ job_id: data.job_id, status: 'pending', created_at: new Date().toISOString() }));
        });

        socket.on('chemtrail:job-cancelled', (data) => {
            dispatch(updateJob({ job_id: data.job_id, status: 'cancelled' }));
        });

        socket.on('chemtrail:historical-scan-complete', () => {
            dispatch(fetchVideoCatalog({ socket }));
        });

        return () => {
            socket.off('chemtrail:pipeline-started');
            socket.off('chemtrail:pipeline-stopped');
            socket.off('chemtrail:job-submitted');
            socket.off('chemtrail:job-cancelled');
            socket.off('chemtrail:historical-scan-complete');
        };
    }, [socket, dispatch]);

    // ==================== Actions ====================

    const handleStartLive = () => {
        if (!selectedCameraId) return;
        setConfirmDialog({
            open: true,
            action: 'start',
            title: t('pipeline.confirm_start_title'),
            message: t('pipeline.confirm_start_message', { camera: selectedCameraId, hours: liveDuration }),
        });
    };

    const handleStopLive = () => {
        setConfirmDialog({
            open: true,
            action: 'stop',
            title: t('pipeline.confirm_stop_title'),
            message: t('pipeline.confirm_stop_message'),
        });
    };

    const handleConfirm = () => {
        const { action } = confirmDialog;
        setConfirmDialog(prev => ({ ...prev, open: false }));

        if (action === 'start') {
            dispatch(startLivePipeline({
                socket,
                cameraId: selectedCameraId,
                durationHours: liveDuration,
                chunkInterval: liveChunkInterval,
                skipStill,
                applyOverlay,
            }));
        } else if (action === 'stop') {
            dispatch(stopLivePipeline({ socket }));
        }
    };

    const handleSubmitLocal = () => {
        if (!localPath) return;
        dispatch(submitLocalJob({ socket, sourcePath: localPath }));
        setLocalPath('');
    };

    const handleSubmitYoutube = () => {
        if (!youtubeUrl) return;
        dispatch(submitYoutubeJob({ socket, youtubeUrl }));
        setYoutubeUrl('');
    };

    const handleCancelJob = (jobId) => {
        dispatch(cancelPipelineJob({ socket, jobId }));
    };

    const handleStartScan = () => {
        if (!scanDirectory) return;
        dispatch(startHistoricalScan({ socket, directory: scanDirectory, recursive: scanRecursive }));
        setScanDirectory('');
    };

    const handleSaveConfig = () => {
        dispatch(updatePipelineConfig({ socket, config: configForm }));
    };

    const handleTabChange = (event, newValue) => {
        setTabValue(newValue);
    };

    // ==================== Stats Cards ====================

    const statsCards = [
        { label: t('pipeline.stats.total_jobs'), value: stats.total_jobs, icon: <StorageIcon />, color: 'primary' },
        { label: t('pipeline.stats.completed'), value: stats.completed_jobs, icon: <CheckCircleIcon />, color: 'success' },
        { label: t('pipeline.stats.failed'), value: stats.failed_jobs, icon: <ErrorIcon />, color: 'error' },
        { label: t('pipeline.stats.running'), value: stats.running_jobs, icon: <PendingIcon />, color: 'info' },
        { label: t('pipeline.stats.total_detections'), value: stats.total_detections, icon: <RadarIcon />, color: 'secondary' },
        { label: t('pipeline.stats.success_rate'), value: `${stats.success_rate}%`, icon: <SpeedIcon />, color: 'warning' },
    ];

    // ==================== Job Columns ====================

    const jobColumns = [
        { field: 'job_id', headerName: 'Job ID', width: 280, renderCell: (params) => (
            <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                {params.value?.substring(0, 8)}...
            </Typography>
        )},
        { field: 'status', headerName: 'Status', width: 130, renderCell: (params) => (
            <Chip
                icon={getStatusIcon(params.value)}
                label={params.value}
                color={getStatusColor(params.value)}
                size="small"
                variant="outlined"
            />
        )},
        { field: 'current_stage', headerName: 'Stage', width: 120, renderCell: (params) => (
            <Typography variant="caption">{getStageLabel(params.value)}</Typography>
        )},
        { field: 'created_at', headerName: 'Created', width: 160, renderCell: (params) => (
            <Typography variant="caption">{params.value ? new Date(params.value).toLocaleString() : '-'}</Typography>
        )},
        { field: 'actions', headerName: 'Actions', width: 100, renderCell: (params) => (
            params.row.status === 'running' || params.row.status === 'pending' ? (
                <Tooltip title={t('pipeline.cancel_job')}>
                    <IconButton size="small" onClick={() => handleCancelJob(params.row.job_id)}>
                        <CancelOutlinedIcon fontSize="small" color="error" />
                    </IconButton>
                </Tooltip>
            ) : null
        )},
    ];

    // ==================== Webcam Source Columns ====================

    const webcamColumns = [
        { field: 'id', headerName: 'ID', width: 150 },
        { field: 'name', headerName: 'Name', width: 200 },
        { field: 'url', headerName: 'URL', width: 300 },
        { field: 'status', headerName: 'Status', width: 120, renderCell: (params) => (
            <Chip label={params.value} size="small"
                color={params.value === 'connected' ? 'success' : 'warning'}
                variant="outlined" />
        )},
        { field: 'actions', headerName: 'Actions', width: 120, renderCell: (params) => (
            <Button
                size="small"
                variant="outlined"
                disabled={livePipelineRunning || params.row.status !== 'connected'}
                onClick={() => setSelectedCameraId(params.row.id)}
            >
                {t('pipeline.use_for_live')}
            </Button>
        )},
    ];

    // ==================== Catalog Columns ====================

    const catalogColumns = [
        { field: 'camera_name', headerName: 'Camera', width: 150 },
        { field: 'source_type', headerName: 'Source', width: 100 },
        { field: 'quality_score', headerName: 'Quality', width: 100, renderCell: (params) => `${params.value || 0}%` },
        { field: 'processing_status', headerName: 'Status', width: 120 },
        { field: 'detection_count', headerName: 'Detections', width: 120 },
        { field: 'chunk_count', headerName: 'Chunks', width: 100 },
        { field: 'created_at', headerName: 'Created', width: 160, renderCell: (params) => (
            params.value ? new Date(params.value).toLocaleDateString() : '-'
        )},
    ];

    return (
        <Paper elevation={3} sx={{ padding: 2 }}>
            {/* Header */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Alert severity="info" sx={{ flex: 1 }}>
                    <AlertTitle>{t('pipeline.title')}</AlertTitle>
                    {t('pipeline.subtitle')}
                </Alert>
                <Tooltip title={t('pipeline.refresh')}>
                    <IconButton onClick={handleRefreshAll} disabled={loading} sx={{ ml: 1 }}>
                        <RefreshIcon />
                    </IconButton>
                </Tooltip>
            </Box>

            {/* Error Display */}
            {error && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => dispatch({ type: 'chemtrailPipeline/clearError' })}>
                    {error}
                </Alert>
            )}

            {/* Live Pipeline Status Banner */}
            <Card sx={{ mb: 2, bgcolor: livePipelineRunning ? 'success.light' : 'action.hover' }}>
                <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            {livePipelineRunning ? (
                                <CircularProgress size={20} thickness={4} color="success" />
                            ) : (
                                <Box sx={{ width: 20, height: 20, borderRadius: '50%', bgcolor: 'grey.400' }} />
                            )}
                            <Typography variant="h6">
                                {livePipelineRunning
                                    ? t('pipeline.live_running', { camera: livePipelineCameraId })
                                    : t('pipeline.live_stopped')}
                            </Typography>
                        </Box>
                        <Stack direction="row" spacing={1}>
                            <Button
                                variant="contained"
                                color="success"
                                startIcon={<PlayArrowIcon />}
                                onClick={handleStartLive}
                                disabled={livePipelineRunning || !selectedCameraId || loading}
                            >
                                {t('pipeline.start_live')}
                            </Button>
                            <Button
                                variant="contained"
                                color="error"
                                startIcon={<StopIcon />}
                                onClick={handleStopLive}
                                disabled={!livePipelineRunning || loading}
                            >
                                {t('pipeline.stop_live')}
                            </Button>
                        </Stack>
                    </Box>
                </CardContent>
            </Card>

            {/* Stats Cards */}
            <Grid container spacing={2} sx={{ mb: 2 }}>
                {statsCards.map((card, index) => (
                    <Grid item xs={6} sm={4} md={2} key={index}>
                        <Card sx={{ height: '100%' }}>
                            <CardContent sx={{ textAlign: 'center', py: 1.5 }}>
                                <Box sx={{ display: 'flex', justifyContent: 'center', mb: 0.5 }}>
                                    {React.cloneElement(card.icon, { color: card.color, fontSize: 'small' })}
                                </Box>
                                <Typography variant="h5" fontWeight="bold" color={`${card.color}.main`}>
                                    {card.value}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                    {card.label}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                ))}
            </Grid>

            {/* Tabs */}
            <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 1 }}>
                <Tabs value={tabValue} onChange={handleTabChange}>
                    <Tab label={t('pipeline.tab_control')} icon={<SettingsIcon />} iconPosition="start" />
                    <Tab label={t('pipeline.tab_cameras')} icon={<VideocamIcon />} iconPosition="start" />
                    <Tab label={t('pipeline.tab_historical')} icon={<FolderOpenIcon />} iconPosition="start" />
                    <Tab label={t('pipeline.tab_configuration')} icon={<SettingsIcon />} iconPosition="start" />
                </Tabs>
            </Box>

            {/* Tab: Control */}
            <TabPanel value={tabValue} index={0}>
                {/* Job Submission */}
                <Grid container spacing={2} sx={{ mb: 2 }}>
                    <Grid item xs={12} md={6}>
                        <Card>
                            <CardContent>
                                <Typography variant="subtitle1" sx={{ mb: 1 }}>
                                    <UploadFileIcon sx={{ verticalAlign: 'middle', mr: 0.5 }} />
                                    {t('pipeline.submit_local_job')}
                                </Typography>
                                <Stack direction="row" spacing={1}>
                                    <TextField
                                        fullWidth
                                        size="small"
                                        placeholder="/path/to/video.mp4"
                                        value={localPath}
                                        onChange={(e) => setLocalPath(e.target.value)}
                                        onKeyDown={(e) => e.key === 'Enter' && handleSubmitLocal()}
                                    />
                                    <Button
                                        variant="contained"
                                        size="small"
                                        onClick={handleSubmitLocal}
                                        disabled={!localPath || loading}
                                    >
                                        {t('pipeline.submit')}
                                    </Button>
                                </Stack>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid item xs={12} md={6}>
                        <Card>
                            <CardContent>
                                <Typography variant="subtitle1" sx={{ mb: 1 }}>
                                    <YouTubeIcon sx={{ verticalAlign: 'middle', mr: 0.5 }} />
                                    {t('pipeline.submit_youtube_job')}
                                </Typography>
                                <Stack direction="row" spacing={1}>
                                    <TextField
                                        fullWidth
                                        size="small"
                                        placeholder="https://youtube.com/watch?v=..."
                                        value={youtubeUrl}
                                        onChange={(e) => setYoutubeUrl(e.target.value)}
                                        onKeyDown={(e) => e.key === 'Enter' && handleSubmitYoutube()}
                                    />
                                    <Button
                                        variant="contained"
                                        size="small"
                                        onClick={handleSubmitYoutube}
                                        disabled={!youtubeUrl || loading}
                                    >
                                        {t('pipeline.submit')}
                                    </Button>
                                </Stack>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>

                {/* Live Pipeline Config */}
                <Card sx={{ mb: 2 }}>
                    <CardContent>
                        <Typography variant="subtitle1" sx={{ mb: 1 }}>
                            {t('pipeline.live_config_title')}
                        </Typography>
                        <Grid container spacing={2}>
                            <Grid item xs={12} sm={6} md={3}>
                                <TextField
                                    fullWidth
                                    size="small"
                                    label={t('pipeline.camera_id')}
                                    value={selectedCameraId}
                                    onChange={(e) => setSelectedCameraId(e.target.value)}
                                    helperText={t('pipeline.camera_id_helper')}
                                />
                            </Grid>
                            <Grid item xs={12} sm={6} md={3}>
                                <TextField
                                    fullWidth
                                    size="small"
                                    type="number"
                                    label={t('pipeline.duration_hours')}
                                    value={liveDuration}
                                    onChange={(e) => setLiveDuration(Number(e.target.value))}
                                    inputProps={{ min: 0.1, max: 24, step: 0.1 }}
                                />
                            </Grid>
                            <Grid item xs={12} sm={6} md={3}>
                                <TextField
                                    fullWidth
                                    size="small"
                                    type="number"
                                    label={t('pipeline.chunk_interval')}
                                    value={liveChunkInterval}
                                    onChange={(e) => setLiveChunkInterval(Number(e.target.value))}
                                    inputProps={{ min: 10, max: 300, step: 5 }}
                                />
                            </Grid>
                            <Grid item xs={12} sm={6} md={3}>
                                <Stack spacing={1} sx={{ mt: 1 }}>
                                    <FormControlLabel
                                        control={<Switch checked={skipStill} onChange={(e) => setSkipStill(e.target.checked)} />}
                                        label={t('pipeline.skip_still')}
                                    />
                                    <FormControlLabel
                                        control={<Switch checked={applyOverlay} onChange={(e) => setApplyOverlay(e.target.checked)} />}
                                        label={t('pipeline.apply_overlay')}
                                    />
                                </Stack>
                            </Grid>
                        </Grid>
                    </CardContent>
                </Card>

                {/* Jobs Table */}
                <Typography variant="subtitle1" sx={{ mb: 1 }}>
                    {t('pipeline.jobs_table_title')}
                </Typography>
                <Box sx={{ height: 350, width: '100%' }}>
                    <DataGrid
                        rows={jobs}
                        columns={jobColumns}
                        getRowId={(row) => row.job_id}
                        pageSizeOptions={[10, 25, 50]}
                        initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
                        disableRowSelectionOnClick
                        density="compact"
                    />
                </Box>
            </TabPanel>

            {/* Tab: Cameras */}
            <TabPanel value={tabValue} index={1}>
                <Alert severity="info" sx={{ mb: 2 }}>
                    {t('pipeline.cameras_tab_subtitle')}
                </Alert>
                <Box sx={{ height: 400, width: '100%' }}>
                    <DataGrid
                        rows={webcamSources}
                        columns={webcamColumns}
                        getRowId={(row) => row.id}
                        pageSizeOptions={[10, 25]}
                        disableRowSelectionOnClick
                        density="compact"
                    />
                </Box>
            </TabPanel>

            {/* Tab: Historical */}
            <TabPanel value={tabValue} index={2}>
                {/* Directory Scan */}
                <Card sx={{ mb: 2 }}>
                    <CardContent>
                        <Typography variant="subtitle1" sx={{ mb: 1 }}>
                            <FolderOpenIcon sx={{ verticalAlign: 'middle', mr: 0.5 }} />
                            {t('pipeline.scan_directory')}
                        </Typography>
                        <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
                            <TextField
                                fullWidth
                                size="small"
                                placeholder="/path/to/video/directory"
                                value={scanDirectory}
                                onChange={(e) => setScanDirectory(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleStartScan()}
                            />
                            <Button
                                variant="contained"
                                size="small"
                                onClick={handleStartScan}
                                disabled={!scanDirectory || loading}
                            >
                                {t('pipeline.scan')}
                            </Button>
                        </Stack>
                        <FormControlLabel
                            control={<Switch checked={scanRecursive} onChange={(e) => setScanRecursive(e.target.checked)} />}
                            label={t('pipeline.recursive')}
                        />
                    </CardContent>
                </Card>

                {/* Video Catalog */}
                <Typography variant="subtitle1" sx={{ mb: 1 }}>
                    {t('pipeline.video_catalog_title')} ({videoCatalog.length})
                </Typography>
                <Box sx={{ height: 350, width: '100%' }}>
                    <DataGrid
                        rows={videoCatalog}
                        columns={catalogColumns}
                        getRowId={(row) => row.id}
                        pageSizeOptions={[10, 25, 50]}
                        disableRowSelectionOnClick
                        density="compact"
                    />
                </Box>
            </TabPanel>

            {/* Tab: Configuration */}
            <TabPanel value={tabValue} index={3}>
                <Card>
                    <CardContent>
                        <Typography variant="subtitle1" sx={{ mb: 2 }}>
                            {t('pipeline.config_title')}
                        </Typography>
                        <Grid container spacing={3}>
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth
                                    size="small"
                                    type="number"
                                    label={t('pipeline.max_concurrent_jobs')}
                                    value={configForm.max_concurrent_jobs ?? config.max_concurrent_jobs}
                                    onChange={(e) => setConfigForm(prev => ({ ...prev, max_concurrent_jobs: Number(e.target.value) }))}
                                    inputProps={{ min: 1, max: 20 }}
                                />
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth
                                    size="small"
                                    type="number"
                                    label={t('pipeline.chunk_duration_seconds')}
                                    value={configForm.chunk_duration_seconds ?? config.chunk_duration_seconds}
                                    onChange={(e) => setConfigForm(prev => ({ ...prev, chunk_duration_seconds: Number(e.target.value) }))}
                                    inputProps={{ min: 5, max: 300 }}
                                />
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth
                                    size="small"
                                    type="number"
                                    label={t('pipeline.chunk_overlap_seconds')}
                                    value={configForm.chunk_overlap_seconds ?? config.chunk_overlap_seconds}
                                    onChange={(e) => setConfigForm(prev => ({ ...prev, chunk_overlap_seconds: Number(e.target.value) }))}
                                    inputProps={{ min: 0, max: 60 }}
                                />
                            </Grid>
                            <Grid item xs={12} sm={6}>
                                <Stack spacing={1} sx={{ mt: 0.5 }}>
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                checked={configForm.enable_weather_enrichment ?? config.enable_weather_enrichment}
                                                onChange={(e) => setConfigForm(prev => ({ ...prev, enable_weather_enrichment: e.target.checked }))}
                                            />
                                        }
                                        label={t('pipeline.enable_weather')}
                                    />
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                checked={configForm.enable_quality_scoring ?? config.enable_quality_scoring}
                                                onChange={(e) => setConfigForm(prev => ({ ...prev, enable_quality_scoring: e.target.checked }))}
                                            />
                                        }
                                        label={t('pipeline.enable_quality_scoring')}
                                    />
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                checked={configForm.skip_still_frames ?? config.skip_still_frames}
                                                onChange={(e) => setConfigForm(prev => ({ ...prev, skip_still_frames: e.target.checked }))}
                                            />
                                        }
                                        label={t('pipeline.skip_still_frames')}
                                    />
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                checked={configForm.apply_overlay ?? config.apply_overlay}
                                                onChange={(e) => setConfigForm(prev => ({ ...prev, apply_overlay: e.target.checked }))}
                                            />
                                        }
                                        label={t('pipeline.apply_overlay')}
                                    />
                                </Stack>
                            </Grid>
                        </Grid>
                        <Box sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end' }}>
                            <Button
                                variant="contained"
                                onClick={handleSaveConfig}
                                disabled={loading}
                            >
                                {t('pipeline.save_config')}
                            </Button>
                        </Box>
                    </CardContent>
                </Card>
            </TabPanel>

            {/* Confirmation Dialog */}
            <Dialog open={confirmDialog.open} onClose={() => setConfirmDialog(prev => ({ ...prev, open: false }))}>
                <DialogTitle>{confirmDialog.title}</DialogTitle>
                <DialogContent>
                    <DialogContentText>{confirmDialog.message}</DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setConfirmDialog(prev => ({ ...prev, open: false }))}>
                        {t('actions.cancel')}
                    </Button>
                    <Button onClick={handleConfirm} variant="contained" color={confirmDialog.action === 'stop' ? 'error' : 'success'}>
                        {confirmDialog.action === 'stop' ? t('pipeline.stop_live') : t('pipeline.start_live')}
                    </Button>
                </DialogActions>
            </Dialog>
        </Paper>
    );
}
