#!/bin/bash

# Build script for Anki MCP Server DXT Package
set -e

echo "🚀 Building Anki MCP Server DXT Package..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Go is installed
if ! command -v go &> /dev/null; then
    print_error "Go is not installed. Please install Go 1.21+ first."
    exit 1
fi

# Check Go version
GO_VERSION=$(go version | awk '{print $3}' | sed 's/go//')
REQUIRED_VERSION="1.21"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$GO_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    print_error "Go version $GO_VERSION is too old. Please install Go $REQUIRED_VERSION or later."
    exit 1
fi

print_success "Go version $GO_VERSION detected"

# Clean previous builds
print_status "Cleaning previous builds..."
rm -rf dxt-package/server/*
rm -f *.dxt

# Update dependencies
print_status "Updating Go dependencies..."
go mod tidy

# Run tests
print_status "Running tests..."
if ! go test -v; then
    print_error "Tests failed. Aborting build."
    exit 1
fi
print_success "All tests passed"

# Build for all platforms
print_status "Building binaries for all platforms..."

# macOS (Intel)
print_status "Building for macOS (Intel)..."
GOOS=darwin GOARCH=amd64 go build -ldflags="-s -w" -o dxt-package/server/mcp-server-anki-go-darwin-amd64 main.go

# macOS (Apple Silicon)
print_status "Building for macOS (Apple Silicon)..."
GOOS=darwin GOARCH=arm64 go build -ldflags="-s -w" -o dxt-package/server/mcp-server-anki-go-darwin-arm64 main.go

# Linux (Intel)
print_status "Building for Linux (Intel)..."
GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o dxt-package/server/mcp-server-anki-go-linux-amd64 main.go

# Linux (ARM64)
print_status "Building for Linux (ARM64)..."
GOOS=linux GOARCH=arm64 go build -ldflags="-s -w" -o dxt-package/server/mcp-server-anki-go-linux-arm64 main.go

# Windows (Intel)
print_status "Building for Windows (Intel)..."
GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o dxt-package/server/mcp-server-anki-go-windows-amd64.exe main.go

# Windows (ARM64)
print_status "Building for Windows (ARM64)..."
GOOS=windows GOARCH=arm64 go build -ldflags="-s -w" -o dxt-package/server/mcp-server-anki-go-windows-arm64.exe main.go

# Create symlinks for the manifest.json
print_status "Creating platform-specific symlinks..."

# Detect current platform and create appropriate symlink
CURRENT_OS=$(uname -s | tr '[:upper:]' '[:lower:]')
CURRENT_ARCH=$(uname -m)

if [ "$CURRENT_OS" = "darwin" ]; then
    if [ "$CURRENT_ARCH" = "arm64" ]; then
        ln -sf mcp-server-anki-go-darwin-arm64 dxt-package/server/mcp-server-anki-go-darwin
    else
        ln -sf mcp-server-anki-go-darwin-amd64 dxt-package/server/mcp-server-anki-go-darwin
    fi
elif [ "$CURRENT_OS" = "linux" ]; then
    if [ "$CURRENT_ARCH" = "aarch64" ]; then
        ln -sf mcp-server-anki-go-linux-arm64 dxt-package/server/mcp-server-anki-go-linux
    else
        ln -sf mcp-server-anki-go-linux-amd64 dxt-package/server/mcp-server-anki-go-linux
    fi
fi

# Create generic symlinks for the manifest
ln -sf mcp-server-anki-go-darwin-amd64 dxt-package/server/mcp-server-anki-go

# Copy manifest and assets
print_status "Copying manifest and assets..."
cp manifest.json dxt-package/

cp icon.png dxt-package/

# Create placeholder screenshot if it doesn't exist
if [ ! -f "assets/screenshots/anki-interface.png" ]; then
    print_warning "Screenshot not found. Creating placeholder..."
    mkdir -p dxt-package/assets/screenshots
    cat > dxt-package/assets/screenshots/anki-interface.png << 'EOF'
# This is a placeholder. Please replace with actual screenshot.
EOF
fi

# Create README for the DXT package
cat > dxt-package/README.md << 'EOF'
# Anki MCP Server - Claude Desktop Extension

This is a Claude Desktop Extension (.dxt) package for the Anki MCP Server.

## Installation

1. Download the `.dxt` file
2. Open Claude Desktop
3. Go to Extensions settings
4. Click "Install Extension" and select the `.dxt` file
5. Configure the AnkiConnect URL (default: http://localhost:8765)

## Requirements

- Anki with AnkiConnect add-on installed and running
- AnkiConnect running on the specified URL

## Features

- Search and browse Anki decks and cards
- Create new flashcards
- Manage card states and tags
- Control Anki GUI for interactive learning
- View statistics and review history

## Support

For issues and questions, visit: https://github.com/cdpath/mcp-server-anki/issues
EOF

# Create the DXT package
print_status "Creating DXT package..."
cd dxt-package

# Create a zip file
zip -r ../anki-mcp-server.dxt . -x "*.DS_Store" "*/.*"

cd ..

# Verify the package
if [ -f "anki-mcp-server.dxt" ]; then
    print_success "DXT package created successfully: anki-mcp-server.dxt"
    print_status "Package size: $(du -h anki-mcp-server.dxt | cut -f1)"
    
    # List contents
    print_status "Package contents:"
    unzip -l anki-mcp-server.dxt | head -20
    
    print_success "🎉 Build completed successfully!"
    print_status "You can now install anki-mcp-server.dxt in Claude Desktop"
else
    print_error "Failed to create DXT package"
    exit 1
fi

# Cleanup
print_status "Cleaning up build artifacts..."
rm -rf dxt-package

print_success "✅ All done! Your DXT package is ready: anki-mcp-server.dxt" 