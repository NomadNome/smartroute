import React, { useState } from 'react';
import RouteForm from './RouteForm';
import RouteCard from './RouteCard';
import LoadingSpinner from './LoadingSpinner';
import './RouteRecommendation.css';

const API_ENDPOINT = 'https://fm5gv3woye.execute-api.us-east-1.amazonaws.com/prod/recommend';

const RouteRecommendation = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [selectedCriterion, setSelectedCriterion] = useState('balanced');

  const handleSubmit = async (formData) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(API_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          origin_address: formData.origin,
          destination_address: formData.destination,
          criterion: selectedCriterion,
        }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message || 'Failed to get route recommendations. Please try again.');
      console.error('API Error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="route-recommendation-container">
      <header className="header">
        <h1>🚇 SmartRoute</h1>
        <p>NYC Subway Route Recommendations with Real-Time Data</p>
      </header>

      <div className="content-wrapper">
        <div className="form-section">
          <RouteForm onSubmit={handleSubmit} loading={loading} />

          <div className="criterion-selector">
            <label>Prioritize:</label>
            <div className="criterion-buttons">
              <button
                className={`criterion-btn ${selectedCriterion === 'safe' ? 'active' : ''}`}
                onClick={() => setSelectedCriterion('safe')}
                disabled={loading}
              >
                🛡️ Safety
              </button>
              <button
                className={`criterion-btn ${selectedCriterion === 'fast' ? 'active' : ''}`}
                onClick={() => setSelectedCriterion('fast')}
                disabled={loading}
              >
                ⚡ Speed
              </button>
              <button
                className={`criterion-btn ${selectedCriterion === 'balanced' ? 'active' : ''}`}
                onClick={() => setSelectedCriterion('balanced')}
                disabled={loading}
              >
                ⚖️ Balanced
              </button>
            </div>
          </div>
        </div>

        <div className="results-section">
          {loading && <LoadingSpinner />}

          {error && (
            <div className="error-message">
              <span>⚠️ {error}</span>
            </div>
          )}

          {result && (
            <div className="results-container">
              <div className="route-summary">
                <h2>Routes from {result.origin_station} to {result.destination_station}</h2>
                <p className="timestamp">
                  Generated {new Date(result.timestamp).toLocaleTimeString()} • {Math.round(result.latency_ms)}ms
                </p>
              </div>

              <div className="routes-grid">
                {result.routes && result.routes.map((route, idx) => (
                  <RouteCard key={idx} route={route} />
                ))}
              </div>

              {result.walking_distances && (
                <div className="walking-info">
                  <p>Walking Distance • Origin: {result.walking_distances.origin_km.toFixed(2)} km • Destination: {result.walking_distances.destination_km.toFixed(2)} km</p>
                </div>
              )}
            </div>
          )}

          {!loading && !error && !result && (
            <div className="empty-state">
              <p>👋 Enter your origin and destination to get started</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default RouteRecommendation;
