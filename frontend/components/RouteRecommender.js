/**
 * RouteRecommender Component - Pure React.createElement (No JSX)
 * Fully compatible with external script loading
 */

const API_ENDPOINT = 'https://6ohbwphgql.execute-api.us-east-1.amazonaws.com/prod/recommend';
const API_KEY = 'vVA3LNSQOK408cy44isS9aLVw9tEEtDb7X5d68dU';

const RouteRecommender = () => {
  const [originAddress, setOriginAddress] = React.useState('');
  const [destinationAddress, setDestinationAddress] = React.useState('');
  const [criterion, setCriterion] = React.useState('balanced');
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [response, setResponse] = React.useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(API_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': API_KEY
        },
        body: JSON.stringify({
          origin_address: originAddress,
          destination_address: destinationAddress,
          criterion: criterion,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || `API error: ${res.status}`);
      }

      const data = await res.json();
      setResponse(data.body ? JSON.parse(data.body) : data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score) => {
    if (score >= 8) return 'score-green';
    if (score >= 6) return 'score-yellow';
    return 'score-red';
  };

  const formatStationsWithTransfers = (route) => {
    /**
     * Format stations list to show transfers clearly.
     * Uses segments data if available, otherwise detects duplicate consecutive stations.
     */

    // If we have segments data, use it to identify transfers
    if (route.segments && Array.isArray(route.segments)) {
      const displayItems = [];
      const transfers = {};

      // Map transfers by station
      for (const segment of route.segments) {
        if (segment.type === 'transfer') {
          transfers[segment.station] = {
            from_line: segment.from_line,
            to_line: segment.to_line
          };
        }
      }

      // Build display items from stations
      for (let i = 0; i < route.stations.length; i++) {
        const station = route.stations[i];

        // Skip duplicate consecutive stations (they'll be handled as transfers)
        if (i > 0 && route.stations[i] === route.stations[i - 1]) {
          continue;
        }

        // Check if this is a transfer point
        if (transfers[station]) {
          const t = transfers[station];
          displayItems.push({
            station: station,
            label: `${station} (${t.from_line}→${t.to_line} transfer)`,
            isTransfer: true
          });
        } else {
          displayItems.push({
            station: station,
            label: station,
            isTransfer: false
          });
        }
      }

      return displayItems;
    }

    // Fallback: detect duplicate consecutive stations
    const displayItems = [];
    for (let i = 0; i < route.stations.length; i++) {
      const station = route.stations[i];

      // Skip duplicate consecutive stations
      if (i > 0 && route.stations[i] === route.stations[i - 1]) {
        // Mark previous item as having a transfer if not already marked
        if (displayItems.length > 0 && !displayItems[displayItems.length - 1].isTransfer) {
          displayItems[displayItems.length - 1].label = station + ' (transfer)';
          displayItems[displayItems.length - 1].isTransfer = true;
        }
        continue;
      }

      displayItems.push({
        station: station,
        label: station,
        isTransfer: false
      });
    }

    return displayItems;
  };

  return React.createElement(
    'div',
    { className: 'route-recommender-container' },
    React.createElement(
      'div',
      { className: 'route-recommender-wrapper' },
      // Header
      React.createElement(
        'div',
        { className: 'route-recommender-header' },
        React.createElement(
          'h1',
          { className: 'route-recommender-title' },
          'SmartRoute'
        ),
        React.createElement(
          'p',
          { className: 'route-recommender-subtitle' },
          'AI-Powered NYC Subway Route Recommendations'
        )
      ),
      // Main Grid
      React.createElement(
        'div',
        { className: 'route-recommender-grid' },
        // Form Section
        React.createElement(
          'div',
          { className: 'route-recommender-form-section' },
          React.createElement(
            'div',
            { className: 'route-recommender-card' },
            React.createElement(
              'h2',
              { className: 'route-recommender-card-title' },
              'Plan Your Route'
            ),
            React.createElement(
              'form',
              { onSubmit: handleSubmit, className: 'route-recommender-form' },
              // Origin Address Input with Suggestions
              React.createElement(
                'div',
                { className: 'form-group' },
                React.createElement(
                  'label',
                  { className: 'form-label' },
                  'Origin Address'
                ),
                React.createElement(window.AddressSuggestions, {
                  value: originAddress,
                  onChange: setOriginAddress,
                  onSelect: (stationName) => {
                    setOriginAddress(stationName);
                  },
                  placeholder: 'e.g., 200 East 42nd Street, New York, NY'
                })
              ),
              // Destination Address Input with Suggestions
              React.createElement(
                'div',
                { className: 'form-group' },
                React.createElement(
                  'label',
                  { className: 'form-label' },
                  'Destination Address'
                ),
                React.createElement(window.AddressSuggestions, {
                  value: destinationAddress,
                  onChange: setDestinationAddress,
                  onSelect: (stationName) => {
                    setDestinationAddress(stationName);
                  },
                  placeholder: 'e.g., 1 Battery Park, New York, NY'
                })
              ),
              // Preference Selection
              React.createElement(
                'div',
                { className: 'form-group' },
                React.createElement(
                  'label',
                  { className: 'form-label' },
                  'Preference'
                ),
                React.createElement(
                  'div',
                  { className: 'radio-group' },
                  ['safe', 'fast', 'balanced'].map((option) =>
                    React.createElement(
                      'label',
                      { key: option, className: 'radio-label' },
                      React.createElement('input', {
                        type: 'radio',
                        name: 'criterion',
                        value: option,
                        checked: criterion === option,
                        onChange: (e) => setCriterion(e.target.value),
                        className: 'radio-input',
                      }),
                      React.createElement(
                        'span',
                        { className: 'radio-text' },
                        option.charAt(0).toUpperCase() + option.slice(1)
                      )
                    )
                  )
                )
              ),
              // Submit Button
              React.createElement('button', {
                type: 'submit',
                disabled: loading,
                className: 'submit-button',
                children: loading ? 'Finding Routes...' : 'Get Recommendations',
              })
            ),
            // Error Message
            error &&
              React.createElement(
                'div',
                { className: 'error-message' },
                React.createElement('p', null, error)
              )
          )
        ),
        // Results Section
        React.createElement(
          'div',
          { className: 'route-recommender-results-section' },
          response
            ? React.createElement(
                'div',
                { className: 'route-recommender-results' },
                // Route Info Card
                React.createElement(
                  'div',
                  { className: 'route-recommender-card' },
                  React.createElement(
                    'div',
                    { className: 'route-info-header' },
                    React.createElement(
                      'h3',
                      { className: 'route-info-title' },
                      'Your Route'
                    ),
                    response.cached &&
                      React.createElement(
                        'span',
                        { className: 'cached-badge' },
                        'Cached'
                      )
                  ),
                  React.createElement(
                    'div',
                    { className: 'route-info-grid' },
                    React.createElement(
                      'div',
                      { className: 'route-info-item' },
                      React.createElement(
                        'p',
                        { className: 'route-info-label' },
                        'From'
                      ),
                      React.createElement(
                        'p',
                        { className: 'route-info-station' },
                        response.origin_station
                      ),
                      React.createElement(
                        'p',
                        { className: 'route-info-distance' },
                        response.walking_distances.origin_km.toFixed(2) + ' km walk'
                      )
                    ),
                    React.createElement(
                      'div',
                      { className: 'route-info-item' },
                      React.createElement(
                        'p',
                        { className: 'route-info-label' },
                        'To'
                      ),
                      React.createElement(
                        'p',
                        { className: 'route-info-station' },
                        response.destination_station
                      ),
                      React.createElement(
                        'p',
                        { className: 'route-info-distance' },
                        response.walking_distances.destination_km.toFixed(2) + ' km walk'
                      )
                    )
                  )
                ),
                // Route Options
                response.routes &&
                  response.routes.map((route, idx) =>
                    React.createElement(
                      'div',
                      { key: idx, className: 'route-recommender-card route-option-card' },
                      // Route Header
                      React.createElement(
                        'div',
                        { className: 'route-header' },
                        React.createElement(
                          'div',
                          null,
                          React.createElement(
                            'h3',
                            { className: 'route-name' },
                            route.name
                          ),
                          React.createElement(
                            'p',
                            { className: 'route-lines' },
                            'Lines: ' + (route.lines && route.lines.length > 0 ? route.lines.join(', ') : 'N/A')
                          )
                        ),
                        React.createElement(
                          'div',
                          { className: 'time-badge' },
                          (route.total_time_minutes !== undefined ? route.total_time_minutes : route.estimated_time_minutes || route.time_minutes || 'N/A') + ' min'
                        )
                      ),
                      // Scores Grid
                      React.createElement(
                        'div',
                        { className: 'scores-grid' },
                        React.createElement(
                          'div',
                          { className: 'score-card ' + getScoreColor(route.safety_score), title: 'Based on crime incidents near stations (lower crime = higher safety score, 0-10)' },
                          React.createElement(
                            'div',
                            { className: 'score-header' },
                            React.createElement('span', { className: 'score-label' }, '🛡️ Safety')
                          ),
                          React.createElement(
                            'p',
                            { className: 'score-value' },
                            route.safety_score.toFixed(1)
                          ),
                          React.createElement(
                            'p',
                            { className: 'score-explanation' },
                            'Crime incidents in area'
                          )
                        ),
                        React.createElement(
                          'div',
                          { className: 'score-card ' + getScoreColor(route.reliability_score), title: 'Based on on-time performance of transit lines (higher reliability = fewer delays, 0-10)' },
                          React.createElement(
                            'div',
                            { className: 'score-header' },
                            React.createElement('span', { className: 'score-label' }, '⏱️ Reliability')
                          ),
                          React.createElement(
                            'p',
                            { className: 'score-value' },
                            route.reliability_score.toFixed(1)
                          ),
                          React.createElement(
                            'p',
                            { className: 'score-explanation' },
                            'On-time performance'
                          )
                        ),
                        React.createElement(
                          'div',
                          { className: 'score-card ' + getScoreColor(route.efficiency_score), title: 'Based on travel time and number of transfers (direct routes = higher efficiency, 0-10)' },
                          React.createElement(
                            'div',
                            { className: 'score-header' },
                            React.createElement('span', { className: 'score-label' }, '⚡ Efficiency')
                          ),
                          React.createElement(
                            'p',
                            { className: 'score-value' },
                            route.efficiency_score.toFixed(1)
                          ),
                          React.createElement(
                            'p',
                            { className: 'score-explanation' },
                            'Travel time & transfers'
                          )
                        )
                      ),
                      // Stations Section
                      React.createElement(
                        'div',
                        { className: 'stations-section' },
                        React.createElement(
                          'p',
                          { className: 'stations-label' },
                          'Stations'
                        ),
                        React.createElement(
                          'div',
                          { className: 'stations-list' },
                          route.stations &&
                            formatStationsWithTransfers(route).map((item, i) =>
                              React.createElement(
                                'span',
                                {
                                  key: i,
                                  className: 'station-badge' + (item.isTransfer ? ' transfer-badge' : '')
                                },
                                item.label
                              )
                            )
                        )
                      ),
                      // Explanation Section
                      React.createElement(
                        'div',
                        { className: 'explanation-section' },
                        React.createElement(
                          'p',
                          { className: 'explanation-text' },
                          route.explanation
                        )
                      )
                    )
                  )
              )
            : React.createElement(
                'div',
                { className: 'route-recommender-card empty-state' },
                React.createElement(
                  'div',
                  { className: 'empty-state-content' },
                  React.createElement(
                    'div',
                    { className: 'empty-state-icon' },
                    '📍'
                  ),
                  React.createElement(
                    'p',
                    { className: 'empty-state-text' },
                    'Enter your starting point and destination to get personalized route recommendations'
                  )
                )
              )
        ),
        // Incidents Feed Section (Right Column)
        React.createElement(
          'div',
          { className: 'route-incidents-section' },
          React.createElement(window.IncidentFeed)
        )
      )
    )
  );
};

// Export for use in HTML
window.RouteRecommender = RouteRecommender;
