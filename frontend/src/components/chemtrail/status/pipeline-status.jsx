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

import React, { useEffect } from 'react';
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
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useSocket } from '../../common/socket.jsx';
import { useDispatch, useSelector } from 'react-redux';
import { fetchFR24Health, fetchFR24Metrics, fetchFLMStatus } from './flights-slice.js';
import HealthAndSafetyIcon from '@mui/icons-material/HealthAndSafety';
import DataUsageIcon from '@mui/icons-material/DataUsage';
import SpeedIcon from '@mui/icons-material/Speed';
import StorageIcon from '@mui/icons-material/Storage';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import WarningIcon from '@mui/icons-material/Warning';
import HelpIcon from '@mui/icons-material/Help';
import RefreshIcon from '@mui/icons-material/Refresh';
import ChipIcon from '@mui/icons-material/Chip';
import MemoryIcon from '@mui/icons-material/Memory';
import IconButton from '@mui/material/IconButton';

export default function PipelineStatus() {
    const { socket } = useSocket();
    const dispatch = useDispatch();
    const { t } = useTranslation('chemtrail');

    const {
        fr24Health,
        fr24Metrics,
        flmStatus,
        loading,
        error,
    } = useSelector((state) => state.chemtrailFlights);

    const handleRefresh = () => {
        dispatch(fetchFR24Health({ socket }));
        dispatch(fetchFR24Metrics({ socket }));
        dispatch(fetchFLMStatus({ socket }));
    };

    useEffect(() => {
        handleRefresh();
        // Auto-refresh every 60 seconds
        const interval = setInterval(handleRefresh, 60000);
        return () => clearInterval(interval);
    }, []);

    const getStatusColor = (status) => {
        switch (status) {
            case 'healthy':
                return 'success';
            case 'degraded':
                return 'warning';
            case 'unhealthy':
                return 'error';
            default:
                return 'default';
        }
    };

    const getStatusIcon = (status) => {
        switch (status) {
            case 'healthy':
                return <CheckCircleIcon color="success" />;
            case 'degraded':
                return <WarningIcon color="warning" />;
            case 'unhealthy':
                return <ErrorIcon color="error" />;
            default:
                return <HelpIcon color="action" />;
        }
    };

    const getCircuitBreakerColor = (state) => {
        switch (state) {
            case 'closed':
                return 'success';
            case 'open':
                return 'error';
            case 'half-open':
                return 'warning';
            default:
                return 'default';
        }
    };

    const getCircuitBreakerLabel = (state) => {
        switch (state) {
            case 'closed':
                return t('status.circuit_breaker_closed');
            case 'open':
                return t('status.circuit_breaker_open');
            case 'half-open':
                return t('status.circuit_breaker_half_open');
            default:
                return state;
        }
    };

    const calculateSuccessRate = () => {
        const total = fr24Metrics.totalRequests || 0;
        const successful = fr24Metrics.successfulRequests || 0;
        if (total === 0) return 100;
        return Math.round((successful / total) * 100);
    };

    const formatLatency = (ms) => {
        if (ms === undefined || ms === null) return '-';
        if (ms < 1000) return `${Math.round(ms)} ms`;
        return `${(ms / 1000).toFixed(1)} s`;
    };

    return (
        <Paper elevation={3} sx={{ padding: 2, marginTop: 0 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Alert severity="info" sx={{ flex: 1 }}>
                    <AlertTitle>{t('status.title')}</AlertTitle>
                    {t('status.subtitle')}
                </Alert>
                <Tooltip title={t('status.refresh')}>
                    <IconButton
                        onClick={handleRefresh}
                        disabled={loading}
                        sx={{ ml: 1 }}
                    >
                        <RefreshIcon />
                    </IconButton>
                </Tooltip>
            </Box>

            {/* Error Display */}
            {error && (
                <Alert severity="error" sx={{ mb: 2 }}>
                    {error}
                </Alert>
            )}

            {loading && <LinearProgress sx={{ mb: 2 }} />}

            <Grid container spacing={3}>
                {/* FR24 Health Status */}
                <Grid item xs={12} md={6}>
                    <Card sx={{ height: '100%' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                                <HealthAndSafetyIcon color="primary" />
                                <Typography variant="h6">
                                    {t('status.fr24_health')}
                                </Typography>
                            </Box>

                            <Stack spacing={2}>
                                {/* Overall Status */}
                                <Box
                                    sx={{
                                        p: 2,
                                        bgcolor: 'action.hover',
                                        borderRadius: 1,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'space-between',
                                    }}
                                >
                                    <Typography variant="subtitle2">
                                        {t('status.overall_status')}
                                    </Typography>
                                    <Chip
                                        icon={getStatusIcon(fr24Health.status)}
                                        label={fr24Health.status || t('status.unknown')}
                                        color={getStatusColor(fr24Health.status)}
                                        variant="filled"
                                    />
                                </Box>

                                {/* Circuit Breaker State */}
                                <Box
                                    sx={{
                                        p: 2,
                                        bgcolor: 'action.hover',
                                        borderRadius: 1,
                                    }}
                                >
                                    <Typography variant="subtitle2" sx={{ mb: 1 }}>
                                        {t('status.circuit_breaker')}
                                    </Typography>
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        <CircularProgress
                                            size={24}
                                            thickness={4}
                                            variant={fr24Health.circuitBreakerState === 'closed' ? 'determinate' : 'indeterminate'}
                                            value={
                                                fr24Health.circuitBreakerState === 'closed' ? 100 :
                                                fr24Health.circuitBreakerState === 'half-open' ? 50 : 0
                                            }
                                            color={getCircuitBreakerColor(fr24Health.circuitBreakerState)}
                                        />
                                        <Chip
                                            label={getCircuitBreakerLabel(fr24Health.circuitBreakerState)}
                                            size="small"
                                            color={getCircuitBreakerColor(fr24Health.circuitBreakerState)}
                                        />
                                    </Box>
                                </Box>

                                {/* Last Check */}
                                <Typography variant="caption" color="text.secondary">
                                    {t('status.last_check')}: {fr24Health.lastCheck ? new Date(fr24Health.lastCheck).toLocaleString() : '-'}
                                </Typography>
                            </Stack>
                        </CardContent>
                    </Card>
                </Grid>

                {/* FR24 Metrics */}
                <Grid item xs={12} md={6}>
                    <Card sx={{ height: '100%' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                                <DataUsageIcon color="secondary" />
                                <Typography variant="h6">
                                    {t('status.metrics')}
                                </Typography>
                            </Box>

                            <Grid container spacing={2}>
                                {/* Total Requests */}
                                <Grid item xs={6}>
                                    <Box
                                        sx={{
                                            p: 2,
                                            bgcolor: 'action.hover',
                                            borderRadius: 1,
                                            textAlign: 'center',
                                        }}
                                    >
                                        <StorageIcon sx={{ mb: 1, color: 'text.secondary' }} />
                                        <Typography variant="h4">{fr24Metrics.totalRequests || 0}</Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            {t('status.total_requests')}
                                        </Typography>
                                    </Box>
                                </Grid>

                                {/* Success Rate */}
                                <Grid item xs={6}>
                                    <Box
                                        sx={{
                                            p: 2,
                                            bgcolor: 'action.hover',
                                            borderRadius: 1,
                                            textAlign: 'center',
                                        }}
                                    >
                                        <CheckCircleIcon sx={{ mb: 1, color: 'success.main' }} />
                                        <Typography variant="h4">{calculateSuccessRate()}%</Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            {t('status.success_rate')}
                                        </Typography>
                                    </Box>
                                </Grid>

                                {/* Average Latency */}
                                <Grid item xs={6}>
                                    <Box
                                        sx={{
                                            p: 2,
                                            bgcolor: 'action.hover',
                                            borderRadius: 1,
                                            textAlign: 'center',
                                        }}
                                    >
                                        <SpeedIcon sx={{ mb: 1, color: 'info.main' }} />
                                        <Typography variant="h4">{formatLatency(fr24Metrics.averageLatency)}</Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            {t('status.avg_latency')}
                                        </Typography>
                                    </Box>
                                </Grid>

                                {/* Cache Hit Rate */}
                                <Grid item xs={6}>
                                    <Box
                                        sx={{
                                            p: 2,
                                            bgcolor: 'action.hover',
                                            borderRadius: 1,
                                            textAlign: 'center',
                                        }}
                                    >
                                        <StorageIcon sx={{ mb: 1, color: 'warning.main' }} />
                                        <Typography variant="h4">
                                            {(() => {
                                                const hits = fr24Metrics.cacheHits || 0;
                                                const misses = fr24Metrics.cacheMisses || 0;
                                                const total = hits + misses;
                                                return total > 0 ? Math.round((hits / total) * 100) : 0;
                                            })()}%
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            {t('status.cache_hit_rate')}
                                        </Typography>
                                    </Box>
                                </Grid>
                            </Grid>

                            <Divider sx={{ my: 2 }} />

                            {/* Detailed Stats */}
                            <Stack spacing={1}>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <Typography variant="body2" color="text.secondary">
                                        {t('status.successful')}
                                    </Typography>
                                    <Typography variant="body2" color="success.main">
                                        {fr24Metrics.successfulRequests || 0}
                                    </Typography>
                                </Box>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <Typography variant="body2" color="text.secondary">
                                        {t('status.failed')}
                                    </Typography>
                                    <Typography variant="body2" color="error.main">
                                        {fr24Metrics.failedRequests || 0}
                                    </Typography>
                                </Box>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <Typography variant="body2" color="text.secondary">
                                        {t('status.cache_hits')}
                                    </Typography>
                                    <Typography variant="body2" color="warning.main">
                                        {fr24Metrics.cacheHits || 0}
                                    </Typography>
                                </Box>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <Typography variant="body2" color="text.secondary">
                                        {t('status.cache_misses')}
                                    </Typography>
                                    <Typography variant="body2">
                                        {fr24Metrics.cacheMisses || 0}
                                    </Typography>
                                </Box>
                            </Stack>
                        </CardContent>
                    </Card>
                </Grid>

                {/* FLM/NPU Status */}
                <Grid item xs={12}>
                    <Card>
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                                <MemoryIcon color="secondary" />
                                <Typography variant="h6">
                                    FLM Server & AMD Ryzen AI NPU
                                </Typography>
                            </Box>

                            <Grid container spacing={2}>
                                {/* Server Connection Status */}
                                <Grid item xs={12} md={4}>
                                    <Box
                                        sx={{
                                            p: 2,
                                            bgcolor: 'action.hover',
                                            borderRadius: 1,
                                            textAlign: 'center',
                                        }}
                                    >
                                        <Typography variant="subtitle2" sx={{ mb: 1 }}>
                                            Server Connection
                                        </Typography>
                                        <Chip
                                            icon={flmStatus.serverConnected ? <CheckCircleIcon /> : <ErrorIcon />}
                                            label={flmStatus.serverConnected ? 'Connected' : 'Disconnected'}
                                            color={flmStatus.serverConnected ? 'success' : 'error'}
                                            variant="filled"
                                        />
                                        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                                            {flmStatus.serverConnected ? flmStatus.availableModels?.length + ' models available' : 'FLM server unavailable'}
                                        </Typography>
                                    </Box>
                                </Grid>

                                {/* Embedding Model */}
                                <Grid item xs={12} md={4}>
                                    <Box
                                        sx={{
                                            p: 2,
                                            bgcolor: 'action.hover',
                                            borderRadius: 1,
                                            textAlign: 'center',
                                        }}
                                    >
                                        <ChipIcon sx={{ mb: 1, color: 'info.main' }} />
                                        <Typography variant="subtitle2" sx={{ mb: 1 }}>
                                            Embedding Model
                                        </Typography>
                                        <Typography variant="body2" fontWeight="medium">
                                            {flmStatus.embeddingModel || 'embed-gemma:300m'}
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            768 dimensions
                                        </Typography>
                                    </Box>
                                </Grid>

                                {/* Vision Model */}
                                <Grid item xs={12} md={4}>
                                    <Box
                                        sx={{
                                            p: 2,
                                            bgcolor: 'action.hover',
                                            borderRadius: 1,
                                            textAlign: 'center',
                                        }}
                                    >
                                        <MemoryIcon sx={{ mb: 1, color: 'primary.main' }} />
                                        <Typography variant="subtitle2" sx={{ mb: 1 }}>
                                            Vision Model
                                        </Typography>
                                        <Typography variant="body2" fontWeight="medium">
                                            {flmStatus.visionModel || 'qwen3vl-it:4b'}
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            AMD Ryzen AI NPU
                                        </Typography>
                                    </Box>
                                </Grid>
                            </Grid>

                            {/* Error Display */}
                            {flmStatus.error && (
                                <Alert severity="error" sx={{ mt: 2 }}>
                                    {flmStatus.error}
                                </Alert>
                            )}

                            {/* Available Models List */}
                            {flmStatus.serverConnected && flmStatus.availableModels && flmStatus.availableModels.length > 0 && (
                                <Box sx={{ mt: 2 }}>
                                    <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
                                        Available Models:
                                    </Typography>
                                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                        {flmStatus.availableModels.map((model) => (
                                            <Chip
                                                key={model}
                                                label={model}
                                                size="small"
                                                variant="outlined"
                                            />
                                        ))}
                                    </Box>
                                </Box>
                            )}
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>
        </Paper>
    );
}
