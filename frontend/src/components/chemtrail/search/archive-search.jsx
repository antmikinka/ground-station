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

import React, { useState, useEffect, useCallback } from 'react';
import {
    Box,
    Paper,
    TextField,
    Button,
    Alert,
    AlertTitle,
    Grid,
    Card,
    CardContent,
    CardMedia,
    Typography,
    Stack,
    CircularProgress,
    InputAdornment,
    Chip,
    IconButton,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import ClearIcon from '@mui/icons-material/Clear';
import PhotoCameraIcon from '@mui/icons-material/PhotoCamera';
import RadarIcon from '@mui/icons-material/Radar';
import { useTranslation } from 'react-i18next';
import { useSocket } from '../../common/socket.jsx';
import { useDispatch, useSelector } from 'react-redux';
import { searchArchive, clearSearchResults } from './detections-slice.js';
import DetectionDetailDialog from './detection-detail-dialog.jsx';

export default function ArchiveSearch() {
    const { socket } = useSocket();
    const dispatch = useDispatch();
    const { t } = useTranslation('chemtrail');
    const [query, setQuery] = useState('');
    const [debouncedQuery, setDebouncedQuery] = useState('');
    const [openDetailDialog, setOpenDetailDialog] = useState(false);

    const {
        loading,
        searchResults,
        error,
    } = useSelector((state) => state.chemtrailDetections);

    // Debounce search query
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedQuery(query);
        }, 500);

        return () => clearTimeout(timer);
    }, [query]);

    // Execute search when debounced query changes
    useEffect(() => {
        if (debouncedQuery.trim()) {
            dispatch(searchArchive({ socket, query: debouncedQuery }));
        } else {
            dispatch(clearSearchResults());
        }
    }, [debouncedQuery, socket]);

    const handleSearch = (e) => {
        e.preventDefault();
        setQuery(e.target.search.value);
    };

    const handleClear = () => {
        setQuery('');
        dispatch(clearSearchResults());
    };

    const handleResultClick = (detection) => {
        // setSelectedDetection would be needed here
        setOpenDetailDialog(true);
    };

    const formatTimestamp = (isoString) => {
        if (!isoString) return '';
        const date = new Date(isoString);
        return date.toLocaleDateString();
    };

    const getResultTypeColor = (type) => {
        switch (type) {
            case 'contrail':
                return 'info';
            case 'cloud':
                return 'default';
            case 'aircraft':
                return 'primary';
            default:
                return 'default';
        }
    };

    return (
        <Paper elevation={3} sx={{ padding: 2, marginTop: 0 }}>
            <Alert severity="info" sx={{ mb: 2 }}>
                <AlertTitle>{t('search.title')}</AlertTitle>
                {t('search.subtitle')}
            </Alert>

            {/* Search Input */}
            <Box
                component="form"
                onSubmit={handleSearch}
                sx={{ mb: 3 }}
            >
                <TextField
                    fullWidth
                    placeholder={t('search.placeholder')}
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    InputProps={{
                        startAdornment: (
                            <InputAdornment position="start">
                                <SearchIcon color="action" />
                            </InputAdornment>
                        ),
                        endAdornment: (
                            <InputAdornment position="end">
                                {loading ? (
                                    <CircularProgress size={20} />
                                ) : query ? (
                                    <IconButton
                                        size="small"
                                        onClick={handleClear}
                                        edge="end"
                                    >
                                        <ClearIcon />
                                    </IconButton>
                                ) : null}
                            </InputAdornment>
                        ),
                    }}
                    sx={{ mb: 2 }}
                />

                <Stack direction="row" spacing={1} justifyContent="center">
                    <Chip
                        label={t('search.example_date')}
                        size="small"
                        onClick={() => setQuery('yesterday contrail')}
                        variant="outlined"
                    />
                    <Chip
                        label={t('search.example_flight')}
                        size="small"
                        onClick={() => setQuery('callsign:AAL123')}
                        variant="outlined"
                    />
                    <Chip
                        label={t('search.example_location')}
                        size="small"
                        onClick={() => setQuery('lat:40.7128 lon:-74.0060 radius:50km')}
                        variant="outlined"
                    />
                </Stack>
            </Box>

            {/* Error Display */}
            {error && (
                <Alert severity="error" sx={{ mb: 2 }}>
                    {error}
                </Alert>
            )}

            {/* Search Results */}
            {searchResults && searchResults.length > 0 && (
                <Box>
                    <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
                        {t('search.results_count', { count: searchResults.length })}
                    </Typography>
                    <Grid container spacing={2}>
                        {searchResults.map((detection) => (
                            <Grid item xs={12} sm={6} md={4} lg={3} key={detection.id}>
                                <Card
                                    sx={{
                                        cursor: 'pointer',
                                        transition: 'transform 0.2s, box-shadow 0.2s',
                                        '&:hover': {
                                            transform: 'translateY(-4px)',
                                            boxShadow: 4,
                                        },
                                    }}
                                    onClick={() => handleResultClick(detection)}
                                >
                                    {/* Placeholder for detection image */}
                                    <Box
                                        sx={{
                                            height: 160,
                                            bgcolor: 'action.hover',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                        }}
                                    >
                                        {detection.image_url ? (
                                            <CardMedia
                                                component="img"
                                                height="160"
                                                image={detection.image_url}
                                                alt={t('search.detection_image')}
                                            />
                                        ) : (
                                            <PhotoCameraIcon sx={{ fontSize: 48, color: 'action.active' }} />
                                        )}
                                    </Box>
                                    <CardContent>
                                        <Stack direction="row" spacing={1} sx={{ mb: 1, flexWrap: 'wrap' }}>
                                            <Chip
                                                label={detection.type}
                                                size="small"
                                                color={getResultTypeColor(detection.type)}
                                            />
                                            {detection.confidence > 0.7 && (
                                                <Chip
                                                    label={`${Math.round(detection.confidence * 100)}%`}
                                                    size="small"
                                                    color="success"
                                                />
                                            )}
                                        </Stack>
                                        <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                                            {formatTimestamp(detection.timestamp)}
                                        </Typography>
                                        {detection.camera_name && (
                                            <Typography
                                                variant="caption"
                                                color="text.secondary"
                                                sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}
                                            >
                                                <PhotoCameraIcon sx={{ fontSize: 14 }} />
                                                {detection.camera_name}
                                            </Typography>
                                        )}
                                        {detection.callsign && (
                                            <Typography
                                                variant="caption"
                                                color="text.secondary"
                                                sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5 }}
                                            >
                                                <RadarIcon sx={{ fontSize: 14 }} />
                                                {detection.callsign}
                                            </Typography>
                                        )}
                                    </CardContent>
                                </Card>
                            </Grid>
                        ))}
                    </Grid>
                </Box>
            )}

            {/* No Results */}
            {debouncedQuery.trim() && !loading && searchResults && searchResults.length === 0 && (
                <Box sx={{ textAlign: 'center', py: 8 }}>
                    <SearchIcon sx={{ fontSize: 64, color: 'action.disabled', mb: 2 }} />
                    <Typography variant="h6" color="text.secondary">
                        {t('search.no_results')}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        {t('search.no_results_hint')}
                    </Typography>
                </Box>
            )}

            {/* Initial State */}
            {!debouncedQuery.trim() && (
                <Box sx={{ textAlign: 'center', py: 8 }}>
                    <SearchIcon sx={{ fontSize: 64, color: 'action.disabled', mb: 2 }} />
                    <Typography variant="h6" color="text.secondary">
                        {t('search.initial_state')}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        {t('search.initial_state_hint')}
                    </Typography>
                </Box>
            )}

            {/* Detail Dialog */}
            <DetectionDetailDialog
                open={openDetailDialog}
                onClose={() => setOpenDetailDialog(false)}
                detection={searchResults?.[0] || null}
            />
        </Paper>
    );
}
