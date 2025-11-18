import React, { useState } from 'react';
import './RouteForm.css';

const RouteForm = ({ onSubmit, loading }) => {
  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [errors, setErrors] = useState({});

  const handleSubmit = (e) => {
    e.preventDefault();
    const newErrors = {};

    if (!origin.trim()) {
      newErrors.origin = 'Please enter an origin address';
    }
    if (!destination.trim()) {
      newErrors.destination = 'Please enter a destination address';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setErrors({});
    onSubmit({
      origin: origin.trim(),
      destination: destination.trim(),
    });
  };

  const handleSwap = () => {
    const temp = origin;
    setOrigin(destination);
    setDestination(temp);
  };

  return (
    <form className="route-form" onSubmit={handleSubmit}>
      <h2>Where are you going?</h2>

      <div className="form-group">
        <label htmlFor="origin">📍 From:</label>
        <input
          id="origin"
          type="text"
          placeholder="e.g., Grand Central Terminal, NYC"
          value={origin}
          onChange={(e) => setOrigin(e.target.value)}
          disabled={loading}
          className={errors.origin ? 'error' : ''}
        />
        {errors.origin && <span className="error-text">{errors.origin}</span>}
      </div>

      <button
        type="button"
        className="swap-button"
        onClick={handleSwap}
        disabled={loading || !origin || !destination}
        title="Swap origin and destination"
      >
        ⇅
      </button>

      <div className="form-group">
        <label htmlFor="destination">🎯 To:</label>
        <input
          id="destination"
          type="text"
          placeholder="e.g., Times Square Station, NYC"
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
          disabled={loading}
          className={errors.destination ? 'error' : ''}
        />
        {errors.destination && <span className="error-text">{errors.destination}</span>}
      </div>

      <button type="submit" className="submit-button" disabled={loading}>
        {loading ? 'Finding Routes...' : 'Get Route Recommendations'}
      </button>

      <div className="form-hints">
        <p>💡 Tip: You can enter full addresses or station names</p>
        <p>⚡ Real-time data updates every minute</p>
      </div>
    </form>
  );
};

export default RouteForm;
