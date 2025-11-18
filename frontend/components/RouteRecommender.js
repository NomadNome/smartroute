/**
 * RouteRecommender Component - Pure React.createElement (No JSX)
 * Fully compatible with external script loading
 */

const API_ENDPOINT = '/api/routes/recommend';

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
        headers: { 'Content-Type': 'application/json' },
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
              // Origin Address Input
              React.createElement(
                'div',
                { className: 'form-group' },
                React.createElement(
                  'label',
                  { className: 'form-label' },
                  'Origin Address'
                ),
                React.createElement('input', {
                  type: 'text',
                  value: originAddress,
                  onChange: (e) => setOriginAddress(e.target.value),
                  placeholder: 'e.g., 200 East 42nd Street, New York, NY',
                  className: 'form-input',
                  required: true,
                })
              ),
              // Destination Address Input
              React.createElement(
                'div',
                { className: 'form-group' },
                React.createElement(
                  'label',
                  { className: 'form-label' },
                  'Destination Address'
                ),
                React.createElement('input', {
                  type: 'text',
                  value: destinationAddress,
                  onChange: (e) => setDestinationAddress(e.target.value),
                  placeholder: 'e.g., 1 Battery Park, New York, NY',
                  className: 'form-input',
                  required: true,
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
                            'Lines: ' + route.line
                          )
                        ),
                        React.createElement(
                          'div',
                          { className: 'time-badge' },
                          route.time_minutes + ' min'
                        )
                      ),
                      // Scores Grid
                      React.createElement(
                        'div',
                        { className: 'scores-grid' },
                        React.createElement(
                          'div',
                          { className: 'score-card ' + getScoreColor(route.safety_score) },
                          React.createElement(
                            'div',
                            { className: 'score-header' },
                            React.createElement('span', { className: 'score-label' }, '🛡️ Safety')
                          ),
                          React.createElement(
                            'p',
                            { className: 'score-value' },
                            route.safety_score.toFixed(1)
                          )
                        ),
                        React.createElement(
                          'div',
                          { className: 'score-card ' + getScoreColor(route.reliability_score) },
                          React.createElement(
                            'div',
                            { className: 'score-header' },
                            React.createElement('span', { className: 'score-label' }, '⏱️ Reliability')
                          ),
                          React.createElement(
                            'p',
                            { className: 'score-value' },
                            route.reliability_score.toFixed(1)
                          )
                        ),
                        React.createElement(
                          'div',
                          { className: 'score-card ' + getScoreColor(route.efficiency_score) },
                          React.createElement(
                            'div',
                            { className: 'score-header' },
                            React.createElement('span', { className: 'score-label' }, '⚡ Efficiency')
                          ),
                          React.createElement(
                            'p',
                            { className: 'score-value' },
                            route.efficiency_score.toFixed(1)
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
                            route.stations.map((station, i) =>
                              React.createElement(
                                'span',
                                { key: i, className: 'station-badge' },
                                station
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
        )
      )
    )
  );
};

// Export for use in HTML
window.RouteRecommender = RouteRecommender;
