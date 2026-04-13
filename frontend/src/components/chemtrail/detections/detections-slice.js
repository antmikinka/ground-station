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

// Async thunks for detections
export const fetchDetections = createAsyncThunk(
    'chemtrailDetections/fetchAll',
    async ({ socket, params = {} }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_request', 'get-chemtrail-detections', params, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to fetch detections'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const fetchDetection = createAsyncThunk(
    'chemtrailDetections/fetchOne',
    async ({ socket, id }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_request', 'get-chemtrail-detection', { id }, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to fetch detection'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const submitDetection = createAsyncThunk(
    'chemtrailDetections/submit',
    async ({ socket, detection }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_submission', 'submit-chemtrail-detection', detection, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to submit detection'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const deleteDetection = createAsyncThunk(
    'chemtrailDetections/delete',
    async ({ socket, id }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_submission', 'delete-chemtrail-detection', { id }, (res) => {
                    if (res.success) {
                        resolve({ id, data: res.data });
                    } else {
                        reject(new Error(res.error || 'Failed to delete detection'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const searchArchive = createAsyncThunk(
    'chemtrailDetections/searchArchive',
    async ({ socket, query }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_request', 'search-chemtrail-archive', { query }, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to search archive'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

const defaultDetection = {
    id: null,
    timestamp: '',
    camera_id: null,
    camera_name: '',
    icao24: '',
    callsign: '',
    type: '',
    confidence: 0,
    correlation_score: null,
    azimuth: null,
    elevation: null,
    estimated_lat: null,
    estimated_lon: null,
    estimated_alt: null,
};

const detectionsSlice = createSlice({
    name: 'chemtrailDetections',
    initialState: {
        detections: [],
        selectedDetection: defaultDetection,
        searchResults: [],
        loading: false,
        error: null,
        status: 'idle',
        filters: {
            camera: 'all',
            dateFrom: '',
            dateTo: '',
            type: 'all',
        },
        pagination: {
            page: 0,
            pageSize: 25,
            total: 0,
        },
    },
    reducers: {
        setDetections: (state, action) => {
            state.detections = action.payload;
        },
        setSelectedDetection: (state, action) => {
            state.selectedDetection = action.payload;
        },
        setSearchResults: (state, action) => {
            state.searchResults = action.payload;
        },
        setLoading: (state, action) => {
            state.loading = action.payload;
        },
        setError: (state, action) => {
            state.error = action.payload;
        },
        setStatus: (state, action) => {
            state.status = action.payload;
        },
        setFilters: (state, action) => {
            state.filters = {
                ...state.filters,
                ...action.payload,
            };
        },
        resetFilters: (state) => {
            state.filters = {
                camera: 'all',
                dateFrom: '',
                dateTo: '',
                type: 'all',
            };
        },
        setPagination: (state, action) => {
            state.pagination = {
                ...state.pagination,
                ...action.payload,
            };
        },
        clearSelectedDetection: (state) => {
            state.selectedDetection = defaultDetection;
        },
        clearSearchResults: (state) => {
            state.searchResults = [];
        },
        addDetection: (state, action) => {
            // Prepend new detection to the list
            const newDetection = action.payload;
            if (newDetection && !state.detections.find(d => d.id === newDetection.id)) {
                state.detections.unshift(newDetection);
            }
        },
    },
    extraReducers: (builder) => {
        builder
            // Fetch detections
            .addCase(fetchDetections.pending, (state) => {
                state.status = 'loading';
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchDetections.fulfilled, (state, action) => {
                state.status = 'succeeded';
                state.loading = false;
                state.detections = action.payload.detections || [];
                state.pagination.total = action.payload.total || action.payload.length || 0;
            })
            .addCase(fetchDetections.rejected, (state, action) => {
                state.status = 'failed';
                state.loading = false;
                state.error = action.payload;
            })
            // Fetch single detection
            .addCase(fetchDetection.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchDetection.fulfilled, (state, action) => {
                state.loading = false;
                state.selectedDetection = action.payload;
            })
            .addCase(fetchDetection.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })
            // Submit detection
            .addCase(submitDetection.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(submitDetection.fulfilled, (state, action) => {
                state.loading = false;
                state.detections = [action.payload, ...state.detections];
            })
            .addCase(submitDetection.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })
            // Delete detection
            .addCase(deleteDetection.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(deleteDetection.fulfilled, (state, action) => {
                state.loading = false;
                state.detections = state.detections.filter(d => d.id !== action.payload.id);
            })
            .addCase(deleteDetection.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })
            // Search archive
            .addCase(searchArchive.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(searchArchive.fulfilled, (state, action) => {
                state.loading = false;
                state.searchResults = action.payload;
            })
            .addCase(searchArchive.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            });
    },
});

export const {
    setDetections,
    setSelectedDetection,
    setSearchResults,
    setLoading,
    setError,
    setStatus,
    setFilters,
    resetFilters,
    setPagination,
    clearSelectedDetection,
    clearSearchResults,
    addDetection,
} = detectionsSlice.actions;

export default detectionsSlice.reducer;
