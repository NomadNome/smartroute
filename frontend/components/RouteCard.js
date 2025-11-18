import React from 'react';
import './RouteCard.css';

const RouteCard = ({ route }) => {
  const getRouteIcon = (name) => {
    if (name.includes('Safe')) return '🛡️';
    if (name.includes('Fast')) return '⚡';
    if (name.includes('Balanced')) return '⚖️';
    return '🚇';
  };

  const getRecommendationBadge = (name) => {
    if (name.includes('Safe')) return 'Safe Route';
    if (name.includes('Fast')) return 'Fastest Route';
    if (name.includes('Balanced')) return 'Best Overall';
    return 'Route';
  };

  const ScoreBar = ({ label, score, color }) => (
    <div className="score-item">
      <div className="score-label">{label}</div>
      <div className="score-bar-container">
        <div
          className={`score-bar ${color}`}
          style={{ width: `${(score / 10) * 100}%` }}
        />
      </div>
      <div className="score-value">{score}/10</div>
    </div>
  );

  return (
    <div className="route-card">
      <div className="card-header">
        <div className="header-left">
          <h3>{getRouteIcon(route.name)} {getRecommendationBadge(route.name)}</h3>
          <span className="badge">{route.name}</span>
        </div>
        <div className="travel-time">
          <div className="time-value">{route.estimated_time_minutes.toFixed(1)}</div>
          <div className="time-label">min</div>
        </div>
      </div>

      {route.travel_time_explanation && (
        <div className="travel-info">
          <p>{route.travel_time_explanation}</p>
        </div>
      )}

      <div className="stations-section">
        <h4>Route:</h4>
        <div className="stations-list">
          {route.stations && route.stations.map((station, idx) => (
            <div key={idx} className="station-item">
              <span className="station-name">{station}</span>
              {route.lines && route.lines[idx] && (
                <span className="line-badge">Line {route.lines[idx]}</span>
              )}
              {idx < route.stations.length - 1 && (
                <span className="arrow">→</span>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="scores-section">
        <h4>Scores:</h4>
        <ScoreBar
          label="Safety"
          score={route.safety_score}
          color="safety"
        />
        <ScoreBar
          label="Reliability"
          score={route.reliability_score}
          color="reliability"
        />
        <ScoreBar
          label="Efficiency"
          score={route.efficiency_score}
          color="efficiency"
        />
      </div>

      <div className="explanation">
        <p>{route.explanation}</p>
      </div>
    </div>
  );
};

export default RouteCard;
