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

// Async thunks for flights
export const fetchLiveFlights = createAsyncThunk(
    'chemtrailFlights/fetchLive',
    async ({ socket }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_request', 'get-live-flights', null, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to fetch live flights'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const fetchFlightDetails = createAsyncThunk(
    'chemtrailFlights/fetchDetails',
    async ({ socket, icao24 }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_request', 'get-flight-details', { icao24 }, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to fetch flight details'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const fetchFlightTrack = createAsyncThunk(
    'chemtrailFlights/fetchTrack',
    async ({ socket, icao24, startTime, endTime }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_request', 'get-flight-track', { icao24, startTime, endTime }, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to fetch flight track'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const fetchFR24Health = createAsyncThunk(
    'chemtrailFlights/fetchFR24Health',
    async ({ socket }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_request', 'get-fr24-health', null, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to fetch FR24 health'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const fetchFR24Metrics = createAsyncThunk(
    'chemtrailFlights/fetchFR24Metrics',
    async ({ socket }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_request', 'get-fr24-metrics', null, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to fetch FR24 metrics'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const fetchFLMStatus = createAsyncThunk(
    'chemtrailFlights/fetchFLMStatus',
    async ({ socket }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_request', 'get-flm-status', null, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to fetch FLM status'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

const flightsSlice = createSlice({
    name: 'chemtrailFlights',
    initialState: {
        flights: [],
        selectedFlight: null,
        flightTrack: [],
        fr24Health: {
            status: 'unknown',
            circuitBreakerState: 'closed',
            lastCheck: null,
        },
        fr24Metrics: {
            totalRequests: 0,
            successfulRequests: 0,
            failedRequests: 0,
            averageLatency: 0,
            cacheHits: 0,
            cacheMisses: 0,
        },
        flmStatus: {
            serverConnected: false,
            embeddingModel: 'embed-gemma:300m',
            visionModel: 'qwen3vl-it:4b',
            availableModels: [],
            error: null,
        },
        loading: false,
        error: null,
        status: 'idle',
        lastUpdated: null,
    },
    reducers: {
        setFlights: (state, action) => {
            state.flights = action.payload;
        },
        setSelectedFlight: (state, action) => {
            state.selectedFlight = action.payload;
        },
        setFlightTrack: (state, action) => {
            state.flightTrack = action.payload;
        },
        setFR24Health: (state, action) => {
            state.fr24Health = action.payload;
        },
        setFR24Metrics: (state, action) => {
            state.fr24Metrics = action.payload;
        },
        setFLMStatus: (state, action) => {
            state.flmStatus = action.payload;
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
        setLastUpdated: (state, action) => {
            state.lastUpdated = action.payload;
        },
        clearSelectedFlight: (state) => {
            state.selectedFlight = null;
            state.flightTrack = [];
        },
        clearFlights: (state) => {
            state.flights = [];
        },
    },
    extraReducers: (builder) => {
        builder
            // Fetch live flights
            .addCase(fetchLiveFlights.pending, (state) => {
                state.status = 'loading';
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchLiveFlights.fulfilled, (state, action) => {
                state.status = 'succeeded';
                state.loading = false;
                state.flights = action.payload.flights || [];
                state.lastUpdated = new Date().toISOString();
            })
            .addCase(fetchLiveFlights.rejected, (state, action) => {
                state.status = 'failed';
                state.loading = false;
                state.error = action.payload;
            })
            // Fetch flight details
            .addCase(fetchFlightDetails.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchFlightDetails.fulfilled, (state, action) => {
                state.loading = false;
                state.selectedFlight = action.payload;
            })
            .addCase(fetchFlightDetails.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })
            // Fetch flight track
            .addCase(fetchFlightTrack.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchFlightTrack.fulfilled, (state, action) => {
                state.loading = false;
                state.flightTrack = action.payload.track || [];
            })
            .addCase(fetchFlightTrack.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })
            // Fetch FR24 health
            .addCase(fetchFR24Health.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchFR24Health.fulfilled, (state, action) => {
                state.loading = false;
                state.fr24Health = action.payload;
            })
            .addCase(fetchFR24Health.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
                state.fr24Health = {
                    status: 'error',
                    circuitBreakerState: 'open',
                    lastCheck: new Date().toISOString(),
                };
            })
            // Fetch FR24 metrics
            .addCase(fetchFR24Metrics.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchFR24Metrics.fulfilled, (state, action) => {
                state.loading = false;
                state.fr24Metrics = action.payload;
            })
            .addCase(fetchFR24Metrics.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })
            // Fetch FLM status
            .addCase(fetchFLMStatus.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchFLMStatus.fulfilled, (state, action) => {
                state.loading = false;
                state.flmStatus = action.payload;
            })
            .addCase(fetchFLMStatus.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
                state.flmStatus = {
                    serverConnected: false,
                    embeddingModel: 'embed-gemma:300m',
                    visionModel: 'qwen3vl-it:4b',
                    availableModels: [],
                    error: action.payload,
                };
            });
    },
});

export const {
    setFlights,
    setSelectedFlight,
    setFlightTrack,
    setFR24Health,
    setFR24Metrics,
    setFLMStatus,
    setLoading,
    setError,
    setStatus,
    setLastUpdated,
    clearSelectedFlight,
    clearFlights,
} = flightsSlice.actions;

export default flightsSlice.reducer;
