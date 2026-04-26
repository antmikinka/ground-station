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

import React, { useState } from 'react';
import {
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    Button,
    TextField,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Box,
    Typography,
    Switch,
    FormControlLabel,
} from '@mui/material';
import { toast } from '../../../utils/toast-with-timestamp.jsx';

export default function CameraAddDialog({ open, onClose, socket }) {
    const [formValues, setFormValues] = useState({
        name: '',
        url: '',
        type: 'mjpeg',
        latitude: 0,
        longitude: 0,
        altitude: 0,
        azimuth: 0,
        elevation: 0,
        fov_horizontal: null,
        fov_vertical: null,
        is_sky_facing: true,
    });

    const handleChange = (field, value) => {
        setFormValues((prev) => ({ ...prev, [field]: value }));
    };

    const handleSubmit = () => {
        if (!formValues.name || !formValues.url) {
            toast.error('Name and URL are required');
            return;
        }

        socket.emit('data_submission', 'submit-chemtrail-camera', formValues, (response) => {
            if (response.success) {
                toast.success(`Camera "${formValues.name}" added successfully`);
                onClose();
            } else {
                toast.error(response.error || 'Failed to add camera');
            }
        });
    };

    const handleClose = () => {
        setFormValues({
            name: '',
            url: '',
            type: 'mjpeg',
            latitude: 0,
            longitude: 0,
            altitude: 0,
            azimuth: 0,
            elevation: 0,
            fov_horizontal: null,
            fov_vertical: null,
            is_sky_facing: true,
        });
        onClose();
    };

    return (
        <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
            <DialogTitle>Add Camera</DialogTitle>
            <DialogContent>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
                    <TextField
                        label="Camera Name"
                        value={formValues.name}
                        onChange={(e) => handleChange('name', e.target.value)}
                        fullWidth
                        required
                    />

                    <TextField
                        label="Stream URL"
                        value={formValues.url}
                        onChange={(e) => handleChange('url', e.target.value)}
                        fullWidth
                        required
                        placeholder="rtsp://... or http://.../stream.mjpg"
                    />

                    <FormControl fullWidth>
                        <InputLabel>Stream Type</InputLabel>
                        <Select
                            value={formValues.type}
                            label="Stream Type"
                            onChange={(e) => handleChange('type', e.target.value)}
                        >
                            <MenuItem value="mjpeg">MJPEG</MenuItem>
                            <MenuItem value="webrtc">WebRTC</MenuItem>
                            <MenuItem value="hls">HLS</MenuItem>
                        </Select>
                    </FormControl>

                    <Typography variant="subtitle2" sx={{ mt: 1 }}>Location & Orientation</Typography>

                    <Box sx={{ display: 'flex', gap: 2 }}>
                        <TextField
                            label="Latitude"
                            type="number"
                            value={formValues.latitude}
                            onChange={(e) => handleChange('latitude', parseFloat(e.target.value))}
                            size="small"
                            fullWidth
                        />
                        <TextField
                            label="Longitude"
                            type="number"
                            value={formValues.longitude}
                            onChange={(e) => handleChange('longitude', parseFloat(e.target.value))}
                            size="small"
                            fullWidth
                        />
                    </Box>

                    <Box sx={{ display: 'flex', gap: 2 }}>
                        <TextField
                            label="Altitude (m)"
                            type="number"
                            value={formValues.altitude}
                            onChange={(e) => handleChange('altitude', parseFloat(e.target.value))}
                            size="small"
                            fullWidth
                        />
                        <TextField
                            label="Azimuth (°)"
                            type="number"
                            value={formValues.azimuth}
                            onChange={(e) => handleChange('azimuth', parseFloat(e.target.value))}
                            size="small"
                            fullWidth
                        />
                    </Box>

                    <Box sx={{ display: 'flex', gap: 2 }}>
                        <TextField
                            label="Elevation (°)"
                            type="number"
                            value={formValues.elevation}
                            onChange={(e) => handleChange('elevation', parseFloat(e.target.value))}
                            size="small"
                            fullWidth
                        />
                        <TextField
                            label="FOV Horizontal (°)"
                            type="number"
                            value={formValues.fov_horizontal || ''}
                            onChange={(e) => handleChange('fov_horizontal', e.target.value ? parseFloat(e.target.value) : null)}
                            size="small"
                            fullWidth
                        />
                    </Box>

                    <FormControlLabel
                        control={
                            <Switch
                                checked={formValues.is_sky_facing}
                                onChange={(e) => handleChange('is_sky_facing', e.target.checked)}
                            />
                        }
                        label="Sky-facing (for contrail detection)"
                    />
                </Box>
            </DialogContent>
            <DialogActions>
                <Button onClick={handleClose} color="inherit">Cancel</Button>
                <Button onClick={handleSubmit} variant="contained">Add Camera</Button>
            </DialogActions>
        </Dialog>
    );
}
