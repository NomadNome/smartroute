#!/bin/bash

# SmartRoute Phase 1 Testing Dashboard Startup Script

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║      SmartRoute Phase 1 Testing Dashboard Launcher        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+ first."
    echo "   Visit: https://nodejs.org/"
    exit 1
fi

echo "✓ Node.js $(node --version)"

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed."
    exit 1
fi

echo "✓ npm $(npm --version)"
echo ""

# Navigate to frontend directory
cd "$(dirname "$0")/../frontend"

echo "📦 Installing dependencies..."
npm install --silent

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              🚀 Starting Dashboard Server                 ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Dashboard will be available at: http://localhost:3001"
echo ""
echo "📍 The dashboard displays:"
echo "   • Real-time station data from DynamoDB"
echo "   • S3 archived data files"
echo "   • Kinesis stream status"
echo "   • CloudWatch Lambda metrics"
echo ""
echo "🔄 Auto-refreshes every 5 seconds"
echo ""
echo "⚠️  Make sure AWS credentials are configured:"
echo "    export AWS_REGION=us-east-1"
echo "    # or use AWS CLI credentials"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server
npm start
