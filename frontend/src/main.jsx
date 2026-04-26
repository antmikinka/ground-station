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


import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './i18n/config.js'
import {createBrowserRouter, RouterProvider} from "react-router";
import {
    SettingsTabLocation,
    SettingsTabRotator,
    SettingsTabPreferences,
    SettingsTabSatellites,
    SettingsTabMaintenance,
    SettingsTabRig,
    SettingsTabTLESources,
    SettingsTabAbout,
    SettingsTabSatelliteGroups,
    SettingsTabCamera,
    SettingsTabSDR
} from "./components/settings/settings.jsx";
import GlobalSatelliteTrackLayout from "./components/overview/main-layout.jsx";
import App from "./App.jsx";
import Layout from "./components/dashboard/dashboard-layout.jsx";
import TargetSatelliteLayout from "./components/target/main-layout.jsx";
import {SocketProvider} from './components/common/socket.jsx';
import { Provider as ReduxProvider} from 'react-redux';
import { PersistGate } from 'redux-persist/integration/react';
import { store, persistor } from './components/common/store.jsx';
import ErrorPage from './components/common/error-page.jsx';
import NotFoundPage from './components/common/not-found-page.jsx';
import MainLayout from "./components/waterfall/main-layout.jsx";
import {WakeLockProvider} from "./components/dashboard/wake-lock-provider.jsx";
import SatelliteInfoPage from "./components/satellites/satellite-info-page.jsx";
import FilebrowserMain from "./components/filebrowser/filebrowser-main.jsx";
import ScheduledObservationsLayout from "./components/scheduler/main-layout.jsx";
import DetectionTable from "./components/chemtrail/detections/detection-table.jsx";
import FlightTable from "./components/chemtrail/flights/flight-table.jsx";
import ArchiveSearch from "./components/chemtrail/search/archive-search.jsx";
import PipelineStatus from "./components/chemtrail/status/pipeline-status.jsx";
import PipelineControl from "./components/chemtrail/pipeline/pipeline-control.jsx";
import WebcamViewer from "./components/chemtrail/webcam/webcam-viewer.jsx";

const enableStrictMode = import.meta.env.VITE_REACT_STRICT_MODE !== 'false';

const router = createBrowserRouter([
    {
        Component: App, // root layout route
        errorElement: <ErrorPage />,
        children: [
            {
                path: "/",
                Component: Layout,
                errorElement: <ErrorPage />,
                children: [
                    {
                        path: "",
                        Component: GlobalSatelliteTrackLayout,
                    },
                    {
                        path: "track",
                        Component: TargetSatelliteLayout,
                    },
                    {
                        path: "waterfall",
                        Component: MainLayout,
                    },
                    {
                        path: "filebrowser",
                        Component: FilebrowserMain,
                    },
                    {
                        path: "scheduler",
                        Component: ScheduledObservationsLayout,
                    },
                    {
                        path: "satellite/:noradId",
                        Component: SatelliteInfoPage,
                    },
                    {
                        path: "satellites",
                        children: [
                            {
                                path: "tlesources",
                                Component: SettingsTabTLESources,
                            },
                            {
                                path: "satellites",
                                Component: SettingsTabSatellites,
                            },
                            {
                                path: "groups",
                                Component: SettingsTabSatelliteGroups,
                            },
                        ],
                    },
                    {
                        path: "settings",
                        children: [
                            {
                                path: "preferences",
                                Component: SettingsTabPreferences,
                            },
                            {
                                path: "location",
                                Component: SettingsTabLocation,
                            },
                            // {
                            //     path: "users",
                            //     Component: SettingsTabUsers,
                            // },
                            {
                                path: "maintenance",
                                Component: SettingsTabMaintenance,
                            },
                            {
                                path: "about",
                                Component: SettingsTabAbout,
                            },
                        ],
                    },
                    {
                        path: "hardware",
                        children: [
                            {
                                path: "rig",
                                Component: SettingsTabRig,
                            },
                            {
                                path: "rotator",
                                Component: SettingsTabRotator,
                            },
                            {
                                path: "cameras",
                                Component: SettingsTabCamera,
                            },
                            {
                                path: "sdrs",
                                Component: SettingsTabSDR,
                            },
                        ],
                    },
                    {
                        path: "chemtrail",
                        children: [
                            {
                                path: "webcam",
                                Component: WebcamViewer,
                            },
                            {
                                path: "cameras",
                                Component: SettingsTabCamera,
                            },
                            {
                                path: "detections",
                                Component: DetectionTable,
                            },
                            {
                                path: "flights",
                                Component: FlightTable,
                            },
                            {
                                path: "search",
                                Component: ArchiveSearch,
                            },
                            {
                                path: "status",
                                Component: PipelineStatus,
                            },
                            {
                                path: "control",
                                Component: PipelineControl,
                            },
                        ],
                    },
                    {
                        path: "*",
                        Component: NotFoundPage,
                    },
                ],
            },
        ],
    },
]);

const app = (
    <ReduxProvider store={store}>
        <PersistGate loading={null} persistor={persistor}>
            <SocketProvider>
                <WakeLockProvider>
                    <RouterProvider router={router} />
                </WakeLockProvider>
            </SocketProvider>
        </PersistGate>
    </ReduxProvider>
);

createRoot(document.getElementById('root')).render(
    enableStrictMode ? <StrictMode>{app}</StrictMode> : app
);
