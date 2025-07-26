#!/bin/bash

# WhatsApp Message Fetcher - Setup Script
# This script sets up the environment for the WhatsApp message fetcher

echo "🚀 Setting up WhatsApp Message Fetcher for Infobip"
echo "================================================="

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if Python is installed
if ! command_exists python3; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check Python version
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✓ Python version: $python_version"

# Check if pip is installed
if ! command_exists pip3; then
    echo "❌ pip3 is not installed. Please install pip."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Create .env file from template if it doesn't exist
if [ ! -f ".env" ]; then
    echo "⚙️ Creating .env file from template..."
    cp env_template.txt .env
    echo "✓ .env file created. Please edit it with your Infobip credentials."
else
    echo "✓ .env file already exists."
fi

# Run setup test
echo "🧪 Running setup tests..."
python test_setup.py

# Check if test passed
if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Setup completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Edit .env file with your Infobip credentials"
    echo "2. Run: python whatsapp_message_fetcher.py"
    echo "3. Configure webhook URL in Infobip dashboard"
    echo "4. Test with: python usage_example.py"
    echo ""
    echo "For local testing, you can use ngrok:"
    echo "- Install: npm install -g ngrok"
    echo "- Run: ngrok http 8000"
    echo "- Use the ngrok URL in your Infobip webhook configuration"
else
    echo "❌ Setup failed. Please check the error messages above."
    exit 1
fi 