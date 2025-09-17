#!/bin/bash
# yt-dlp Update and Dependency Management Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if Docker Compose is available
check_docker_compose() {
    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker compose"
    elif command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    else
        print_error "Docker Compose is not available."
        exit 1
    fi
}

# Update yt-dlp in import worker container
update_ytdlp_container() {
    print_status "Updating yt-dlp in import worker container..."
    
    if docker ps | grep -q meatlizard-import-worker; then
        # Update yt-dlp to latest version
        docker exec meatlizard-import-worker pip install --upgrade yt-dlp
        
        # Verify installation
        YTDLP_VERSION=$(docker exec meatlizard-import-worker yt-dlp --version)
        print_success "yt-dlp updated to version: $YTDLP_VERSION"
        
        # Test basic functionality
        print_status "Testing yt-dlp functionality..."
        if docker exec meatlizard-import-worker yt-dlp --help > /dev/null 2>&1; then
            print_success "yt-dlp is working correctly"
        else
            print_error "yt-dlp test failed"
            return 1
        fi
    else
        print_warning "Import worker container is not running"
        return 1
    fi
}

# Update yt-dlp extractors and dependencies
update_extractors() {
    print_status "Updating yt-dlp extractors and dependencies..."
    
    if docker ps | grep -q meatlizard-import-worker; then
        # Update optional dependencies for better extractor support
        docker exec meatlizard-import-worker pip install --upgrade \
            mutagen \
            pycryptodome \
            websockets \
            brotli \
            certifi \
            requests
        
        print_success "yt-dlp dependencies updated"
    else
        print_warning "Import worker container is not running"
    fi
}

# Clear yt-dlp cache
clear_cache() {
    print_status "Clearing yt-dlp cache..."
    
    if docker ps | grep -q meatlizard-import-worker; then
        docker exec meatlizard-import-worker rm -rf /app/cache/yt-dlp-cache
        docker exec meatlizard-import-worker mkdir -p /app/cache/yt-dlp-cache
        print_success "yt-dlp cache cleared"
    else
        print_warning "Import worker container is not running"
    fi
}

# Test supported platforms
test_platforms() {
    print_status "Testing supported platforms..."
    
    if ! docker ps | grep -q meatlizard-import-worker; then
        print_warning "Import worker container is not running"
        return 1
    fi
    
    # Test URLs for different platforms (using --simulate to avoid actual downloads)
    declare -A test_urls=(
        ["YouTube"]="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        ["TikTok"]="https://www.tiktok.com/@example/video/1234567890"
        ["Instagram"]="https://www.instagram.com/p/example/"
        ["Twitter"]="https://twitter.com/example/status/1234567890"
    )
    
    for platform in "${!test_urls[@]}"; do
        url="${test_urls[$platform]}"
        print_status "Testing $platform support..."
        
        if docker exec meatlizard-import-worker yt-dlp --simulate --quiet "$url" 2>/dev/null; then
            print_success "$platform: ✅ Supported"
        else
            print_warning "$platform: ❌ May have issues"
        fi
    done
}

# Rebuild import worker with latest yt-dlp
rebuild_import_worker() {
    print_status "Rebuilding import worker with latest yt-dlp..."
    
    check_docker_compose
    
    # Stop import worker
    $DOCKER_COMPOSE_CMD -f infra/video-platform-dev.docker-compose.yml stop import-worker
    
    # Rebuild the image
    $DOCKER_COMPOSE_CMD -f infra/video-platform-dev.docker-compose.yml build --no-cache import-worker
    
    # Start import worker
    $DOCKER_COMPOSE_CMD -f infra/video-platform-dev.docker-compose.yml up -d import-worker
    
    # Wait for service to be ready
    print_status "Waiting for import worker to be ready..."
    sleep 10
    
    if docker ps | grep -q meatlizard-import-worker; then
        print_success "Import worker rebuilt and started successfully"
        
        # Show new version
        YTDLP_VERSION=$(docker exec meatlizard-import-worker yt-dlp --version)
        print_success "New yt-dlp version: $YTDLP_VERSION"
    else
        print_error "Failed to start import worker after rebuild"
        return 1
    fi
}

# Show current yt-dlp status
show_status() {
    print_status "Current yt-dlp Status:"
    echo ""
    
    if docker ps | grep -q meatlizard-import-worker; then
        echo "📦 Container Status: Running"
        
        YTDLP_VERSION=$(docker exec meatlizard-import-worker yt-dlp --version 2>/dev/null || echo "Unknown")
        echo "🔢 yt-dlp Version: $YTDLP_VERSION"
        
        PYTHON_VERSION=$(docker exec meatlizard-import-worker python --version 2>/dev/null || echo "Unknown")
        echo "🐍 Python Version: $PYTHON_VERSION"
        
        # Check cache size
        CACHE_SIZE=$(docker exec meatlizard-import-worker du -sh /app/cache 2>/dev/null | cut -f1 || echo "Unknown")
        echo "💾 Cache Size: $CACHE_SIZE"
        
        # Check available extractors count
        EXTRACTOR_COUNT=$(docker exec meatlizard-import-worker yt-dlp --list-extractors 2>/dev/null | wc -l || echo "Unknown")
        echo "🔧 Available Extractors: $EXTRACTOR_COUNT"
    else
        echo "📦 Container Status: Not Running"
    fi
    
    echo ""
}

# Show help
show_help() {
    echo "yt-dlp Update and Management Script"
    echo "=================================="
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  update      Update yt-dlp to latest version"
    echo "  rebuild     Rebuild import worker with latest yt-dlp"
    echo "  clear-cache Clear yt-dlp cache"
    echo "  test        Test platform support"
    echo "  status      Show current yt-dlp status"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 update"
    echo "  $0 rebuild"
    echo "  $0 test"
    echo ""
}

# Main execution
main() {
    case "${1:-status}" in
        "update")
            show_status
            update_ytdlp_container
            update_extractors
            show_status
            ;;
        "rebuild")
            rebuild_import_worker
            show_status
            ;;
        "clear-cache")
            clear_cache
            ;;
        "test")
            test_platforms
            ;;
        "status")
            show_status
            ;;
        "help"|"-h"|"--help")
            show_help
            ;;
        *)
            print_error "Unknown command: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"