#!/bin/bash
# Easy Docker deployment script for fact-checking backend

set -e

echo "Fact-Checking Database Backend - Docker Deployment"
echo "=================================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "ERROR: Docker Compose is not available. Please install Docker Compose."
    exit 1
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p data logs documents

# Check if we have documents to process
DOC_COUNT=$(find documents -name "*.txt" -o -name "*.pdf" -o -name "*.docx" -o -name "*.csv" 2>/dev/null | wc -l || echo 0)
echo "Found $DOC_COUNT documents to process"

if [ "$DOC_COUNT" -eq 0 ]; then
    echo "WARNING: No documents found in documents/ folder"
    echo "   Add your documents (.txt, .pdf, .docx, .csv) to the documents/ folder"
    echo "   Or use the provided sample_facts.txt for testing"
fi

# Set port from environment or default
PORT=${PORT:-8080}
export PORT

echo "Building Docker image..."
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

$COMPOSE_CMD build

echo "Starting services..."
$COMPOSE_CMD up -d

echo ""
echo "Deployment complete!"
echo ""
echo "API Server: http://localhost:$PORT"
echo "Health Check: http://localhost:$PORT/health" 
echo "Database Stats: http://localhost:$PORT/stats"
echo ""
echo "Management commands:"
echo "  View logs:       $COMPOSE_CMD logs -f"
echo "  Stop services:   $COMPOSE_CMD down"
echo "  Restart:         $COMPOSE_CMD restart"
echo "  Shell access:    $COMPOSE_CMD exec fact-check-api /bin/bash"
echo ""
echo "To process new documents:"
echo "  1. Add files to documents/ folder"
echo "  2. Restart the container: $COMPOSE_CMD restart"
echo ""

# Wait a moment and check if services are healthy
echo "Checking service health..."
sleep 10

if curl -s -f "http://localhost:$PORT/health" > /dev/null; then
    echo "API server is healthy and ready!"
else
    echo "WARNING: API server may still be starting up..."
    echo "   Check logs: $COMPOSE_CMD logs fact-check-api"
fi