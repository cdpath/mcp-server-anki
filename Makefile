.PHONY: build test clean run help

# Default target
help:
	@echo "Available targets:"
	@echo "  build    - Build the Go binary"
	@echo "  test     - Run tests"
	@echo "  run      - Run the server (stdio transport)"
	@echo "  run-http - Run the server (HTTP transport on :8080)"
	@echo "  help     - Show this help message"

# Build the binary
build:
	go build -o mcp-server-anki-go main.go
	@echo "Binary built: mcp-server-anki-go"

# Run tests
test:
	go test -v
	@echo "Tests completed"

# Run with stdio transport
run: build
	./mcp-server-anki-go

# Run with HTTP transport
run-http: build
	./mcp-server-anki-go -http :8080

# Install dependencies
deps:
	go mod tidy
	@echo "Dependencies updated"

# Build for different platforms
build-all: deps
	GOOS=linux GOARCH=amd64 go build -o mcp-server-anki-go-linux-amd64 main.go
	GOOS=darwin GOARCH=amd64 go build -o mcp-server-anki-go-darwin-amd64 main.go
	GOOS=darwin GOARCH=arm64 go build -o mcp-server-anki-go-darwin-arm64 main.go
	GOOS=windows GOARCH=amd64 go build -o mcp-server-anki-go-windows-amd64.exe main.go
	@echo "Multi-platform binaries built"

# Development mode (with hot reload if available)
dev:
	@echo "Starting development server..."
	@echo "Note: Go doesn't have built-in hot reload, but you can use tools like 'air'"
	@echo "Install air: go install github.com/cosmtrek/air@latest"
	@echo "Then run: air"

# Build DXT extension package
dxt: deps
	@echo "Building DXT extension package..."
	./build-dxt.sh

# Build everything (binary + DXT package)
all: build dxt
	@echo "All builds completed!" 