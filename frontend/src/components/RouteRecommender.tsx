'use client';

import React, { useState } from 'react';
import { MapPin, Zap, Shield, Clock } from 'lucide-react';

interface Route {
  name: string;
  stations: string[];
  line: string;
  time_minutes: number;
  safety_score: number;
  reliability_score: number;
  efficiency_score: number;
  explanation: string;
}

interface RouteResponse {
  routes: Route[];
  origin_station: string;
  destination_station: string;
  origin_address: string;
  destination_address: string;
  walking_distances: {
    origin_km: number;
    destination_km: number;
  };
  cached: boolean;
}

const API_ENDPOINT = 'https://ch39ie1me9.execute-api.us-east-1.amazonaws.com/prod/routes/recommend';

export default function RouteRecommender() {
  const [originAddress, setOriginAddress] = useState('');
  const [destinationAddress, setDestinationAddress] = useState('');
  const [criterion, setCriterion] = useState<'safe' | 'fast' | 'balanced'>('balanced');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<RouteResponse | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(API_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
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
      setResponse(JSON.parse(data.body) || data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 8) return 'text-green-600 bg-green-50';
    if (score >= 6) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">SmartRoute</h1>
          <p className="text-xl text-gray-600">AI-Powered NYC Subway Route Recommendations</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Input Form */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow-lg p-6 sticky top-6">
              <h2 className="text-2xl font-bold mb-6 text-gray-900">Plan Your Route</h2>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Origin Address
                  </label>
                  <input
                    type="text"
                    value={originAddress}
                    onChange={(e) => setOriginAddress(e.target.value)}
                    placeholder="e.g., Times Square, NYC"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Destination Address
                  </label>
                  <input
                    type="text"
                    value={destinationAddress}
                    onChange={(e) => setDestinationAddress(e.target.value)}
                    placeholder="e.g., Brooklyn Bridge, NYC"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">
                    Preference
                  </label>
                  <div className="space-y-2">
                    {(['safe', 'fast', 'balanced'] as const).map((option) => (
                      <label key={option} className="flex items-center cursor-pointer">
                        <input
                          type="radio"
                          name="criterion"
                          value={option}
                          checked={criterion === option}
                          onChange={(e) => setCriterion(e.target.value as typeof criterion)}
                          className="w-4 h-4 text-blue-600"
                        />
                        <span className="ml-3 text-sm text-gray-700 capitalize">{option}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-bold py-3 rounded-lg transition duration-200"
                >
                  {loading ? 'Finding Routes...' : 'Get Recommendations'}
                </button>
              </form>

              {error && (
                <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              )}
            </div>
          </div>

          {/* Results */}
          <div className="lg:col-span-2">
            {response ? (
              <div className="space-y-4">
                {/* Route Info */}
                <div className="bg-white rounded-lg shadow-lg p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-bold text-gray-900">Your Route</h3>
                    {response.cached && (
                      <span className="text-xs bg-blue-100 text-blue-800 px-3 py-1 rounded-full">
                        Cached
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-gray-600">From</p>
                      <p className="font-semibold text-gray-900">{response.origin_station}</p>
                      <p className="text-xs text-gray-500">
                        {response.walking_distances.origin_km.toFixed(2)} km walk
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-600">To</p>
                      <p className="font-semibold text-gray-900">{response.destination_station}</p>
                      <p className="text-xs text-gray-500">
                        {response.walking_distances.destination_km.toFixed(2)} km walk
                      </p>
                    </div>
                  </div>
                </div>

                {/* Routes Cards */}
                {response.routes.map((route, idx) => (
                  <div
                    key={idx}
                    className="bg-white rounded-lg shadow-lg p-6 border-l-4 border-blue-500 hover:shadow-xl transition"
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <h3 className="text-xl font-bold text-gray-900">{route.name}</h3>
                        <p className="text-sm text-gray-600">Lines: {route.line}</p>
                      </div>
                      <div className="bg-blue-100 text-blue-800 px-4 py-2 rounded-full font-bold">
                        {route.time_minutes} min
                      </div>
                    </div>

                    {/* Scores */}
                    <div className="grid grid-cols-3 gap-4 mb-4">
                      <div className={`p-3 rounded-lg ${getScoreColor(route.safety_score)}`}>
                        <div className="flex items-center gap-2 mb-1">
                          <Shield size={16} />
                          <span className="text-xs font-semibold">Safety</span>
                        </div>
                        <p className="text-lg font-bold">{route.safety_score.toFixed(1)}</p>
                      </div>

                      <div className={`p-3 rounded-lg ${getScoreColor(route.reliability_score)}`}>
                        <div className="flex items-center gap-2 mb-1">
                          <Clock size={16} />
                          <span className="text-xs font-semibold">Reliability</span>
                        </div>
                        <p className="text-lg font-bold">{route.reliability_score.toFixed(1)}</p>
                      </div>

                      <div className={`p-3 rounded-lg ${getScoreColor(route.efficiency_score)}`}>
                        <div className="flex items-center gap-2 mb-1">
                          <Zap size={16} />
                          <span className="text-xs font-semibold">Efficiency</span>
                        </div>
                        <p className="text-lg font-bold">{route.efficiency_score.toFixed(1)}</p>
                      </div>
                    </div>

                    {/* Stations */}
                    <div className="mb-4">
                      <p className="text-xs font-semibold text-gray-600 mb-2">Stations</p>
                      <div className="flex flex-wrap gap-2">
                        {route.stations.map((station, i) => (
                          <span key={i} className="text-xs bg-gray-100 text-gray-700 px-3 py-1 rounded-full">
                            {station}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Explanation */}
                    <div className="bg-gray-50 p-4 rounded-lg">
                      <p className="text-sm text-gray-700 italic">{route.explanation}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="bg-white rounded-lg shadow-lg p-12 text-center">
                <MapPin size={48} className="mx-auto text-gray-400 mb-4" />
                <p className="text-gray-600 text-lg">
                  Enter your starting point and destination to get personalized route recommendations
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
