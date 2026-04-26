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
    Box,
    Paper,
    Alert,
    AlertTitle,
    Typography,
    Button,
    Stack,
    Chip,
    IconButton,
    Tooltip,
    Grid,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import AddIcon from '@mui/icons-material/Add';
import VideocamIcon from '@mui/icons-material/Videocam';
import { useTranslation } from 'react-i18next';
import { useSocket } from '../../common/socket.jsx';
import { useDispatch, useSelector } from 'react-redux';
import {
    fetchChemtrailCameras,
    fetchWebcamSources,
    setLatestDetection,
} from './webcam-slice.js';
import WebcamCard from './webcam-card.jsx';
import CameraAddDialog from './camera-add-dialog.jsx';
import { fetchPipelineStatus } from '../pipeline/pipeline-slice.js';

export default function WebcamViewer() {
    const { socket } = useSocket();
    const dispatch = useDispatch();
    const { t } = useTranslation('chemtrail');
    const [openAddDialog, setOpenAddDialog] = useState(false);
    const [autoRefresh, setAutoRefresh] = useState(true);

    const {
        cameras,
        webcamSources,
        loading,
    } = useSelector((state) => state.chemtrailWebcam || {});

    const {
        livePipelineRunning,
        livePipelineCameraId,
    } = useSelector((state) => state.chemtrailPipeline || {});

    // Fetch cameras on mount
    useEffect(() => {
        dispatch(fetchChemtrailCameras({ socket }));
        dispatch(fetchWebcamSources({ socket }));
    }, []);

    // Auto-refresh pipeline status every 10 seconds
    useEffect(() => {
        if (!autoRefresh) return;

        dispatch(fetchPipelineStatus({ socket }));

        const interval = setInterval(() => {
            dispatch(fetchPipelineStatus({ socket }));
        }, 10000);

        return () => clearInterval(interval);
    }, [autoRefresh, socket, dispatch]);

    const handleRefresh = () => {
        dispatch(fetchChemtrailCameras({ socket }));
        dispatch(fetchWebcamSources({ socket }));
    };

    // Combine chemtrail cameras and webcam sources
    const allSources = [
        ...cameras.map((c) => ({ ...c, sourceType: 'chemtrail' })),
        ...webcamSources.map((s) => ({ ...s, sourceType: 'webcam' })),
    ];

    // Deduplicate by ID
    const uniqueSources = [];
    const seenIds = new Set();
    for (const source of allSources) {
        const id = source.id || source.url;
        if (!seenIds.has(id)) {
            seenIds.add(id);
            uniqueSources.push(source);
        }
    }

    const activeCount = uniqueSources.filter((s) => s.status === 'active').length;
    const processingCount = livePipelineRunning ? 1 : 0;

    return (
        <Paper elevation={3} sx={{ padding: 2, marginTop: 0 }}>
            <Alert severity="info" sx={{ mb: 2 }}>
                <AlertTitle>Live Webcam Viewer</AlertTitle>
                Monitor webcam feeds and contrail detections in real time. Start live processing pipeline directly from any camera feed.
            </Alert>

            {/* Toolbar */}
            <Box sx={{ display: 'flex', gap: 2, mb: 2, alignItems: 'center', flexWrap: 'wrap' }}>
                <Button
                    variant="contained"
                    startIcon={<AddIcon />}
                    onClick={() => setOpenAddDialog(true)}
                >
                    Add Camera
                </Button>
                <Button
                    variant="outlined"
                    startIcon={<RefreshIcon />}
                    onClick={handleRefresh}
                    disabled={loading}
                >
                    Refresh
                </Button>

                <Stack direction="row" spacing={1} sx={{ ml: 'auto' }}>
                    <Chip
                        icon={<VideocamIcon />}
                        label={`${uniqueSources.length} cameras`}
                        size="small"
                        variant="outlined"
                    />
                    {activeCount > 0 && (
                        <Chip
                            label={`${activeCount} active`}
                            size="small"
                            color="success"
                            variant="outlined"
                        />
                    )}
                    {processingCount > 0 && (
                        <Chip
                            label="Processing"
                            size="small"
                            color="warning"
                            variant="filled"
                        />
                    )}
                    <Tooltip title={autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh OFF'}>
                        <Chip
                            label={`Auto: ${autoRefresh ? 'ON' : 'OFF'}`}
                            size="small"
                            clickable
                            onClick={() => setAutoRefresh(!autoRefresh)}
                            color={autoRefresh ? 'primary' : 'default'}
                            variant={autoRefresh ? 'filled' : 'outlined'}
                        />
                    </Tooltip>
                </Stack>
            </Box>

            {/* Camera Grid */}
            {uniqueSources.length > 0 ? (
                <Grid container spacing={2}>
                    {uniqueSources.map((camera) => (
                        <Grid size={{ xs: 12, sm: 6, md: 4, lg: 3 }} key={camera.id || camera.url}>
                            <WebcamCard
                                camera={camera}
                                pipelineRunning={livePipelineRunning}
                                pipelineCameraId={livePipelineCameraId}
                            />
                        </Grid>
                    ))}
                </Grid>
            ) : (
                <Box
                    sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        py: 8,
                        gap: 2,
                    }}
                >
                    <VideocamIcon sx={{ fontSize: 64, color: 'text.disabled' }} />
                    <Typography variant="h6" color="text.secondary">
                        No cameras configured
                    </Typography>
                    <Typography variant="body2" color="text.disabled">
                        Add a camera to start monitoring for contrail detections
                    </Typography>
                    <Button
                        variant="contained"
                        startIcon={<AddIcon />}
                        onClick={() => setOpenAddDialog(true)}
                        sx={{ mt: 2 }}
                    >
                        Add Camera
                    </Button>
                </Box>
            )}

            {/* Add Camera Dialog */}
            <CameraAddDialog
                open={openAddDialog}
                onClose={() => setOpenAddDialog(false)}
                socket={socket}
            />
        </Paper>
    );
}
