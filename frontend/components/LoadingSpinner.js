import React from 'react';
import './LoadingSpinner.css';

const LoadingSpinner = () => (
  <div className="loading-container">
    <div className="spinner">
      <div className="spinner-circle"></div>
      <div className="spinner-circle"></div>
      <div className="spinner-circle"></div>
    </div>
    <p className="loading-text">Finding the best routes for you...</p>
    <p className="loading-subtext">Querying real-time MTA data</p>
  </div>
);

export default LoadingSpinner;
