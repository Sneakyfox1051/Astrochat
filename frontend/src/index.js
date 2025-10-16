/**
 * AstroBot Frontend - React Application Entry Point
 * 
 * This is the main entry point for the AstroBot React application.
 * It initializes the React app and renders the main AstroBotUI component.
 * 
 * Features:
 * - React 18 with createRoot API
 * - Strict mode for development
 * - Global CSS imports
 * - Main component rendering
 * 
 * @fileoverview Main application entry point
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import AstroBotUI from './components/AstroBotUI';

// Create React root and render the main application
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <AstroBotUI />
  </React.StrictMode>
);

