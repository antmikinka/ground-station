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

export const fetchPipelineStatus = createAsyncThunk(
    'chemtrailPipeline/fetchStatus',
    async ({ socket }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_request', 'get-pipeline-status', {}, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to fetch pipeline status'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const fetchPipelineStats = createAsyncThunk(
    'chemtrailPipeline/fetchStats',
    async ({ socket }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_request', 'get-pipeline-stats', {}, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to fetch pipeline stats'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const fetchPipelineConfig = createAsyncThunk(
    'chemtrailPipeline/fetchConfig',
    async ({ socket }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_request', 'get-pipeline-config', {}, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to fetch pipeline config'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const updatePipelineConfig = createAsyncThunk(
    'chemtrailPipeline/updateConfig',
    async ({ socket, config }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_submission', 'update-pipeline-config', config, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to update pipeline config'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const startLivePipeline = createAsyncThunk(
    'chemtrailPipeline/startLive',
    async ({ socket, cameraId, durationHours = 1, chunkInterval = 30, skipStill = true, applyOverlay = false }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_submission', 'start-live-pipeline', {
                    camera_id: cameraId,
                    duration_hours: durationHours,
                    chunk_interval: chunkInterval,
                    skip_still: skipStill,
                    apply_overlay: applyOverlay,
                }, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to start live pipeline'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const stopLivePipeline = createAsyncThunk(
    'chemtrailPipeline/stopLive',
    async ({ socket }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_submission', 'stop-live-pipeline', {}, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to stop live pipeline'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const submitLocalJob = createAsyncThunk(
    'chemtrailPipeline/submitLocal',
    async ({ socket, sourcePath, metadata = {} }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_submission', 'submit-local-job', {
                    source_path: sourcePath,
                    metadata,
                }, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to submit local job'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const submitYoutubeJob = createAsyncThunk(
    'chemtrailPipeline/submitYoutube',
    async ({ socket, youtubeUrl }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_submission', 'submit-youtube-job', {
                    youtube_url: youtubeUrl,
                }, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to submit YouTube job'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const cancelPipelineJob = createAsyncThunk(
    'chemtrailPipeline/cancelJob',
    async ({ socket, jobId }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_submission', 'cancel-pipeline-job', { job_id: jobId }, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to cancel job'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const fetchVideoCatalog = createAsyncThunk(
    'chemtrailPipeline/fetchCatalog',
    async ({ socket, limit = 100, offset = 0 }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_request', 'get-video-catalog', { limit, offset }, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to fetch video catalog'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const startHistoricalScan = createAsyncThunk(
    'chemtrailPipeline/startHistoricalScan',
    async ({ socket, directory, recursive = true }, { rejectWithValue }) => {
        try {
            return await new Promise((resolve, reject) => {
                socket.emit('data_submission', 'start-historical-scan', {
                    directory,
                    recursive,
                }, (res) => {
                    if (res.success) {
                        resolve(res.data);
                    } else {
                        reject(new Error(res.error || 'Failed to start historical scan'));
                    }
                });
            });
        } catch (error) {
            return rejectWithValue(error.message);
        }
    }
);

export const fetchWebcamSources = createAsyncThunk(
    'chemtrailPipeline/fetchWebcamSources',
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

// ==================== Slice ====================

const pipelineSlice = createSlice({
    name: 'chemtrailPipeline',
    initialState: {
        jobs: [],
        currentJob: null,
        livePipelineRunning: false,
        livePipelineCameraId: null,
        config: {
            max_concurrent_jobs: 3,
            stage_timeouts: {},
            enable_weather_enrichment: true,
            enable_quality_scoring: true,
            skip_still_frames: true,
            apply_overlay: false,
            chunk_duration_seconds: 30,
            chunk_overlap_seconds: 5,
        },
        stats: {
            total_jobs: 0,
            completed_jobs: 0,
            failed_jobs: 0,
            running_jobs: 0,
            pending_jobs: 0,
            cancelled_jobs: 0,
            total_detections: 0,
            success_rate: 0,
        },
        videoCatalog: [],
        webcamSources: [],
        loading: false,
        error: null,
        status: 'idle',
    },
    reducers: {
        setPipelineRunning: (state, action) => {
            state.livePipelineRunning = action.payload;
        },
        setLivePipelineCameraId: (state, action) => {
            state.livePipelineCameraId = action.payload;
        },
        addJob: (state, action) => {
            state.jobs.unshift(action.payload);
        },
        updateJob: (state, action) => {
            const index = state.jobs.findIndex(j => j.job_id === action.payload.job_id);
            if (index !== -1) {
                state.jobs[index] = { ...state.jobs[index], ...action.payload };
            }
        },
        removeJob: (state, action) => {
            state.jobs = state.jobs.filter(j => j.job_id !== action.payload);
        },
        setVideoCatalog: (state, action) => {
            state.videoCatalog = action.payload;
        },
        setWebcamSources: (state, action) => {
            state.webcamSources = action.payload;
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
            // Fetch pipeline status
            .addCase(fetchPipelineStatus.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchPipelineStatus.fulfilled, (state, action) => {
                state.loading = false;
                state.jobs = action.payload.jobs || [];
                state.livePipelineRunning = action.payload.pipeline_running || false;
            })
            .addCase(fetchPipelineStatus.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })
            // Fetch pipeline stats
            .addCase(fetchPipelineStats.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchPipelineStats.fulfilled, (state, action) => {
                state.loading = false;
                state.stats = action.payload;
            })
            .addCase(fetchPipelineStats.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })
            // Fetch pipeline config
            .addCase(fetchPipelineConfig.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(fetchPipelineConfig.fulfilled, (state, action) => {
                state.loading = false;
                state.config = action.payload;
            })
            .addCase(fetchPipelineConfig.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })
            // Update pipeline config
            .addCase(updatePipelineConfig.fulfilled, (state) => {
                // Config updated, will be refreshed on next fetch
            })
            // Start live pipeline
            .addCase(startLivePipeline.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(startLivePipeline.fulfilled, (state, action) => {
                state.loading = false;
                state.livePipelineRunning = true;
                state.livePipelineCameraId = action.payload.camera_id;
            })
            .addCase(startLivePipeline.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })
            // Stop live pipeline
            .addCase(stopLivePipeline.pending, (state) => {
                state.loading = true;
                state.error = null;
            })
            .addCase(stopLivePipeline.fulfilled, (state) => {
                state.loading = false;
                state.livePipelineRunning = false;
                state.livePipelineCameraId = null;
            })
            .addCase(stopLivePipeline.rejected, (state, action) => {
                state.loading = false;
                state.error = action.payload;
            })
            // Submit local job
            .addCase(submitLocalJob.fulfilled, (state, action) => {
                if (action.payload.job_id) {
                    state.jobs.unshift({
                        job_id: action.payload.job_id,
                        status: 'pending',
                        current_stage: 'acquisition',
                        created_at: new Date().toISOString(),
                    });
                }
            })
            // Cancel job
            .addCase(cancelPipelineJob.fulfilled, (state) => {
                // Job status will be updated via real-time events
            })
            // Fetch video catalog
            .addCase(fetchVideoCatalog.fulfilled, (state, action) => {
                state.videoCatalog = action.payload || [];
            })
            // Fetch webcam sources
            .addCase(fetchWebcamSources.fulfilled, (state, action) => {
                state.webcamSources = action.payload || [];
            });
    },
});

export const {
    setPipelineRunning,
    setLivePipelineCameraId,
    addJob,
    updateJob,
    removeJob,
    setVideoCatalog,
    setWebcamSources,
    setLoading,
    setError,
    clearError,
} = pipelineSlice.actions;

export default pipelineSlice.reducer;
