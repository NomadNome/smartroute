/**
 * IncidentFeed Component
 * Real-time live feed of NYC crime/311 incidents
 * Shows latest incidents from DynamoDB as they're aggregated
 */

// Local proxy endpoint (avoids CORS issues)
const INCIDENTS_API_URL = '/api/incidents/latest';

window.IncidentFeed = class IncidentFeed extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      incidents: [],
      loading: true,
      error: null,
      filter: 'all', // all, crime, 311
      autoRefresh: true,
      lastUpdated: null
    };
    this.refreshInterval = null;
  }

  componentDidMount() {
    this.fetchIncidents();
    // Auto-refresh every 60 seconds
    this.refreshInterval = setInterval(() => {
      if (this.state.autoRefresh) {
        this.fetchIncidents();
      }
    }, 60000);
  }

  componentWillUnmount() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
  }

  fetchIncidents = async () => {
    try {
      this.setState({ loading: true, error: null });

      const response = await fetch(INCIDENTS_API_URL, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      // Parse incidents from response
      const incidents = data.incidents || [];

      this.setState({
        incidents: incidents,
        loading: false,
        lastUpdated: new Date()
      });

    } catch (err) {
      console.error('Error fetching incidents:', err);
      this.setState({
        error: 'Unable to load incidents',
        loading: false
      });
    }
  }

  getIncidentColor = (type) => {
    if (type === 'crime') return '#ef4444';
    if (type === '311') return '#f59e0b';
    return '#6b7280';
  }

  getIncidentIcon = (type, subtype) => {
    if (type === 'crime') {
      if (subtype && subtype.toLowerCase().includes('assault')) return '⚠️';
      if (subtype && subtype.toLowerCase().includes('theft')) return '🚨';
      return '🛑';
    }
    return '📢';
  }

  formatTime = (timestamp) => {
    if (!timestamp) return 'Just now';
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diff = now - date;

      const minutes = Math.floor(diff / 60000);
      const hours = Math.floor(diff / 3600000);
      const days = Math.floor(diff / 86400000);

      if (minutes < 1) return 'Just now';
      if (minutes < 60) return `${minutes}m ago`;
      if (hours < 24) return `${hours}h ago`;
      if (days < 7) return `${days}d ago`;

      return date.toLocaleDateString();
    } catch (e) {
      return 'Recently';
    }
  }

  filterIncidents = () => {
    const { incidents, filter } = this.state;
    if (filter === 'all') return incidents;
    return incidents.filter(inc => inc.type === filter);
  }

  toggleAutoRefresh = () => {
    this.setState(prev => ({ autoRefresh: !prev.autoRefresh }));
  }

  render() {
    const { loading, error, filter, autoRefresh, lastUpdated } = this.state;
    const filtered = this.filterIncidents();

    return React.createElement('div', { className: 'incident-feed-container' },
      // Header
      React.createElement('div', { className: 'incident-feed-header' },
        React.createElement('div', { className: 'incident-feed-title' },
          React.createElement('span', { className: 'incident-feed-icon' }, '📍'),
          React.createElement('h2', null, 'Live NYC Incidents')
        ),
        React.createElement('div', { className: 'incident-feed-controls' },
          React.createElement('button',
            {
              className: `incident-filter ${filter === 'all' ? 'active' : ''}`,
              onClick: () => this.setState({ filter: 'all' })
            },
            'All'
          ),
          React.createElement('button',
            {
              className: `incident-filter ${filter === 'crime' ? 'active' : ''}`,
              onClick: () => this.setState({ filter: 'crime' })
            },
            '🛑 Crime'
          ),
          React.createElement('button',
            {
              className: `incident-filter ${filter === '311' ? 'active' : ''}`,
              onClick: () => this.setState({ filter: '311' })
            },
            '📢 311'
          ),
          React.createElement('button',
            {
              className: `incident-refresh ${autoRefresh ? 'active' : ''}`,
              onClick: this.toggleAutoRefresh,
              title: 'Toggle auto-refresh'
            },
            autoRefresh ? '🔄' : '⏸'
          )
        )
      ),

      // Status bar
      React.createElement('div', { className: 'incident-feed-status' },
        React.createElement('span', null,
          `${filtered.length} ${filter === 'all' ? 'incident' : filter}${filtered.length !== 1 ? 's' : ''}`
        ),
        React.createElement('span', null,
          lastUpdated ? `Updated ${this.formatTime(lastUpdated)}` : 'Loading...'
        )
      ),

      // Feed list
      React.createElement('div', { className: 'incident-feed-list' },
        loading && !this.state.incidents.length ?
          React.createElement('div', { className: 'incident-feed-loading' },
            React.createElement('div', { className: 'spinner' }),
            'Loading incidents...'
          ) :
          error && !filtered.length ?
            React.createElement('div', { className: 'incident-feed-error' }, error) :
            filtered.length === 0 ?
              React.createElement('div', { className: 'incident-feed-empty' },
                'No incidents to display'
              ) :
              filtered.map((incident, idx) =>
                React.createElement('div',
                  {
                    key: idx,
                    className: 'incident-item',
                    style: { borderLeft: `4px solid ${this.getIncidentColor(incident.type)}` }
                  },
                  React.createElement('div', { className: 'incident-item-header' },
                    React.createElement('span', { className: 'incident-icon' },
                      this.getIncidentIcon(incident.type, incident.subtype)
                    ),
                    React.createElement('div', { className: 'incident-meta' },
                      React.createElement('span', { className: 'incident-type' },
                        incident.type === 'crime' ? '🛑 Crime' : '📢 311 Complaint'
                      ),
                      React.createElement('span', { className: 'incident-time' },
                        this.formatTime(incident.timestamp)
                      )
                    )
                  ),
                  React.createElement('div', { className: 'incident-item-content' },
                    React.createElement('p', { className: 'incident-location' },
                      incident.location || incident.station
                    ),
                    incident.subtype &&
                      React.createElement('p', { className: 'incident-description' },
                        incident.subtype
                      ),
                    incident.details &&
                      React.createElement('p', { className: 'incident-details' },
                        incident.details
                      )
                  )
                )
              )
        )
    );
  }
};
