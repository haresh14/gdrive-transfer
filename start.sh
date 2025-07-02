#!/bin/bash

# Google Drive Transfer - Docker Setup Script
echo "🚀 Google Drive Transfer Docker Setup"
echo "======================================"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create data directory if it doesn't exist
if [ ! -d "data" ]; then
    echo "📁 Creating data directory..."
    mkdir data
    echo "✅ Data directory created"
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Creating from example..."
    if [ -f "env.example" ]; then
        cp env.example .env
        echo "✅ .env file created from example"
        echo ""
        echo "🔧 IMPORTANT: Please edit the .env file with your actual credentials:"
        echo "   - Set GDRIVE_SOURCE_FOLDER_ID to your Google Drive folder ID"
        echo "   - Set GDRIVE_CREDENTIALS_JSON to your Google Cloud credentials JSON"
        echo "   - Set GDRIVE_DESTINATION_PARENT_ID to your Google Drive folder ID"
        echo ""
        echo "After editing .env, run this script again to start the container."
        exit 0
    else
        echo "❌ env.example file not found. Please create a .env file manually."
        exit 1
    fi
fi

# Validate .env file has required variables
if ! grep -q "GDRIVE_SOURCE_FOLDER_ID=" .env || ! grep -q "GDRIVE_CREDENTIALS_JSON=" .env; then
    echo "❌ .env file is missing required variables. Please check your configuration."
    exit 1
fi

# Check if credentials look like defaults
if grep -q "your_folder_id_here" .env || grep -q "your_client_id" .env; then
    echo "⚠️  It looks like you haven't updated the .env file with your actual credentials."
    echo "Please edit .env and replace the example values with your real credentials."
    exit 0
fi

echo "🔧 Configuration looks good!"
echo ""

# Ask user how they want to run
echo "How would you like to run the transfer?"
echo "1) Interactive mode (see logs in real-time, stops when complete)"
echo "2) Background mode (detached, stops when complete)"
echo "3) One-time run (run once and auto-remove container)"
echo ""
read -p "Choose an option (1-3): " choice

case $choice in
    1)
        echo "🚀 Starting in interactive mode..."
        docker-compose up --build
        ;;
    2)
        echo "🚀 Starting in background mode..."
        docker-compose up --build -d
        echo "✅ Container started in background"
        echo "📊 View logs with: docker-compose logs -f"
        echo "🛑 Stop with: docker-compose down"
        ;;
    3)
        echo "🚀 Running one-time transfer..."
        docker-compose run --rm gdrive-transfer
        ;;
    *)
        echo "❌ Invalid option. Please run the script again."
        exit 1
        ;;
esac

echo ""
echo "🎉 Setup complete!"
echo "📁 Logs and tokens are saved in the ./data directory"
echo "📖 For more information, see DOCKER_README.md" 