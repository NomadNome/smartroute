/**
 * AddressSuggestions Component - Pure React.createElement (No JSX)
 * Provides autocomplete suggestions for NYC subway addresses
 * Converts user addresses to nearby stations with walking distances
 *
 * Features:
 * - Debounced address input (300ms delay)
 * - Dropdown suggestions showing top 3 nearby stations
 * - Walking distance to each station
 * - Lines available at each station
 * - Keyboard navigation support
 * - Selection handler to populate parent form
 */

const AddressSuggestions = ({ value, onChange, onSelect, placeholder }) => {
  const [suggestions, setSuggestions] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [showSuggestions, setShowSuggestions] = React.useState(false);
  const [selectedIndex, setSelectedIndex] = React.useState(-1);
  const [error, setError] = React.useState(null);
  const debounceTimer = React.useRef(null);

  // AWS API Gateway endpoint for station suggestions
  const API_ENDPOINT = 'https://6ohbwphgql.execute-api.us-east-1.amazonaws.com/prod/stations/suggest';
  const API_KEY = 'vVA3LNSQOK408cy44isS9aLVw9tEEtDb7X5d68dU';

  /**
   * Fetch station suggestions for a given address
   */
  const fetchSuggestions = React.useCallback(
    async (address) => {
      if (!address || address.trim().length < 3) {
        setSuggestions([]);
        setShowSuggestions(false);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const encodedAddress = encodeURIComponent(address);
        const response = await fetch(`${API_ENDPOINT}?address=${encodedAddress}`, {
          headers: {
            'x-api-key': API_KEY
          }
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || 'Failed to fetch suggestions');
        }

        const data = await response.json();

        // Handle response format (might be wrapped in body)
        const responseData = data.body ? JSON.parse(data.body) : data;

        if (responseData.success && responseData.suggestions) {
          setSuggestions(responseData.suggestions);
          setShowSuggestions(true);
          setSelectedIndex(-1);
        } else {
          setError(responseData.error || 'No suggestions found');
          setSuggestions([]);
        }
      } catch (err) {
        console.error('Error fetching suggestions:', err);
        setError('Could not fetch suggestions');
        setSuggestions([]);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  /**
   * Handle input change with debouncing
   */
  const handleInputChange = (e) => {
    const inputValue = e.target.value;
    onChange(inputValue);

    // Clear existing debounce timer
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }

    // Set new debounce timer (300ms delay)
    debounceTimer.current = setTimeout(() => {
      fetchSuggestions(inputValue);
    }, 300);
  };

  /**
   * Handle suggestion selection
   */
  const handleSelectSuggestion = (suggestion) => {
    const stationName = suggestion.station_name;
    onChange(stationName);
    onSelect(stationName);
    setShowSuggestions(false);
    setSuggestions([]);
    setSelectedIndex(-1);
  };

  /**
   * Handle keyboard navigation in suggestions dropdown
   */
  const handleKeyDown = (e) => {
    if (!showSuggestions || suggestions.length === 0) {
      if (e.key === 'Enter' && value) {
        setShowSuggestions(false);
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex((prev) =>
          prev < suggestions.length - 1 ? prev + 1 : prev
        );
        break;

      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : -1));
        break;

      case 'Enter':
        e.preventDefault();
        if (selectedIndex >= 0) {
          handleSelectSuggestion(suggestions[selectedIndex]);
        }
        break;

      case 'Escape':
        e.preventDefault();
        setShowSuggestions(false);
        setSelectedIndex(-1);
        break;

      default:
        break;
    }
  };

  /**
   * Format walking time nicely
   */
  const formatWalkingTime = (minutes) => {
    if (minutes <= 1) return '1 min walk';
    return `${minutes} min walk`;
  };

  /**
   * Format lines display
   */
  const formatLines = (lines) => {
    if (!lines || lines.length === 0) return '';
    if (lines.length === 1) return lines[0];
    return lines.join(', ');
  };

  return React.createElement(
    'div',
    { className: 'address-suggestions-container' },
    // Input field
    React.createElement('input', {
      type: 'text',
      value: value,
      onChange: handleInputChange,
      onKeyDown: handleKeyDown,
      onFocus: () => {
        if (suggestions.length > 0) {
          setShowSuggestions(true);
        }
      },
      placeholder: placeholder || 'e.g., 200 East 42nd Street, New York, NY',
      className: 'address-input',
      required: true,
      autoComplete: 'off' // Disable browser autocomplete
    }),

    // Loading indicator
    loading &&
      React.createElement(
        'div',
        { className: 'suggestions-loading' },
        '⏳ Finding nearby stations...'
      ),

    // Error message
    error &&
      React.createElement(
        'div',
        { className: 'suggestions-error' },
        '⚠️ ' + error
      ),

    // Suggestions dropdown
    showSuggestions &&
      suggestions.length > 0 &&
      React.createElement(
        'div',
        { className: 'suggestions-dropdown' },
        suggestions.map((suggestion, index) =>
          React.createElement(
            'div',
            {
              key: suggestion.station_name,
              className:
                'suggestion-item' +
                (index === selectedIndex ? ' suggestion-item-selected' : ''),
              onClick: () => handleSelectSuggestion(suggestion),
              onMouseEnter: () => setSelectedIndex(index)
            },
            // Station name
            React.createElement(
              'div',
              { className: 'suggestion-name' },
              suggestion.station_name
            ),
            // Walking time and lines
            React.createElement(
              'div',
              { className: 'suggestion-meta' },
              React.createElement(
                'span',
                { className: 'suggestion-walking-time' },
                '🚶 ' + formatWalkingTime(suggestion.walking_time_minutes)
              ),
              React.createElement(
                'span',
                { className: 'suggestion-lines' },
                '🚇 Lines: ' + formatLines(suggestion.lines)
              )
            )
          )
        )
      ),

    // Empty state - no suggestions found
    showSuggestions &&
      !loading &&
      suggestions.length === 0 &&
      !error &&
      React.createElement(
        'div',
        { className: 'suggestions-empty' },
        'No stations found nearby'
      )
  );
};

// Export for use in HTML
window.AddressSuggestions = AddressSuggestions;
