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

import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';

// ==================== Async Thunks ====================

export const fetchChemtrailCameras = createAsyncThunk(
    'chemtrailWebcam/fetchCameras',
    async ({ socket }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_request', 'get-chemtrail-cameras', {}, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to fetch chemtrail cameras'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const fetchWebcamSources = createAsyncThunk(
    'chemtrailWebcam/fetchWebcamSources',
    async ({ socket }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_request', 'get-webcam-sources', {}, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to fetch webcam sources'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const fetchLatestDetection = createAsyncThunk(
    'chemtrailWebcam/fetchLatestDetection',
    async ({ socket, cameraId }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_request', 'get-detections', { camera: cameraId, limit: 1 }, (res) => {
                    if (res.success) {
                        resolve(res.data?.[0] || null);
                    } else {
                        reject(new Error(res.error || 'Failed to fetch latest detection'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

// ==================== Slice ====================

const chemtrailWebcamSlice = createSlice({
    name: 'chemtrailWebcam',
    initialState: {
        cameras: [],
        webcamSources: [],
        latestDetections: {},
        loading: false,
        error: null,
        status: 'idle',
        refreshInterval: null,
    },
    reducers: {
        setCameras: (state, action) => {
            state.cameras = action.payload;
        },
        setWebcamSources: (state, action) => {
            state.webcamSources = action.payload;
        },
        setLatestDetection: (state, action) => {
            const { cameraId, detection } = action.payload;
            state.latestDetections[cameraId] = detection;
        },
        setRefreshInterval: (state, action) => {
            state.refreshInterval = action.payload;
        },
        setLoading: (state, action) => {
            state.loading = action.payload;
        },
        setError: (state, action) => {
            state.error = action.payload;
        },
        clearError: (state) => {
            state.error = null;
        },
    },
    extraReducers: (builder) => {
        builder
            .addCase(fetchChemtrailCameras.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchChemtrailCameras.fulfilled, (state, action) => {
                state.loading = false;
                state.cameras = action.payload || [];
            })
            .addCase(fetchChemtrailCameras.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })
            .addCase(fetchWebcamSources.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchWebcamSources.fulfilled, (state, action) => {
                state.loading = false;
                state.webcamSources = action.payload || [];
            })
            .addCase(fetchWebcamSources.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })
            .addCase(fetchLatestDetection.fulfilled, (state, action) => {
                // Detection data stored by camera ID key
            });
    },
});

export const {
    setCameras,
    setWebcamSources,
    setLatestDetection,
    setRefreshInterval,
    setLoading,
    setError,
    clearError,
} = chemtrailWebcamSlice.actions;

export default chemtrailWebcamSlice.reducer;
