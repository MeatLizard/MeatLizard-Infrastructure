#!/bin/bash
# Video Platform Development Environment Setup Script

set -e

echo "🎬 Setting up Video Platform Development Environment..."

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

# Check if Docker is installed and running
check_docker() {
    print_status "Checking Docker installation..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    
    print_success "Docker is installed and running"
}

# Check if Docker Compose is available
check_docker_compose() {
    print_status "Checking Docker Compose..."
    
    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker compose"
    elif command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    else
        print_error "Docker Compose is not available. Please install Docker Compose."
        exit 1
    fi
    
    print_success "Docker Compose is available: $DOCKER_COMPOSE_CMD"
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    mkdir -p infra/postgres/data
    mkdir -p infra/redis/data
    mkdir -p infra/minio/data
    mkdir -p infra/nginx/cache
    mkdir -p infra/grafana/data
    mkdir -p infra/prometheus/data
    mkdir -p uploads
    mkdir -p temp
    mkdir -p logs
    
    print_success "Directories created"
}

# Setup environment file
setup_environment() {
    print_status "Setting up environment configuration..."
    
    if [ ! -f ".env" ]; then
        if [ -f "infra/.env.video-platform" ]; then
            cp infra/.env.video-platform .env
            print_success "Environment file created from template"
        else
            print_warning "No environment template found. Please create .env file manually."
        fi
    else
        print_warning ".env file already exists. Skipping environment setup."
    fi
}

# Generate encryption key if needed
generate_encryption_key() {
    print_status "Checking encryption key..."
    
    if grep -q "your_base64_encryption_key_here" .env 2>/dev/null; then
        print_status "Generating new encryption key..."
        
        # Generate a random 32-byte key and encode it in base64
        if command -v openssl &> /dev/null; then
            NEW_KEY=$(openssl rand -base64 32)
            sed -i.bak "s/your_base64_encryption_key_here/$NEW_KEY/" .env
            print_success "Encryption key generated and updated in .env"
        else
            print_warning "OpenSSL not found. Please manually generate a 32-byte base64 key for PAYLOAD_ENCRYPTION_KEY"
        fi
    fi
}

# Generate JWT secret key if needed
generate_jwt_secret() {
    print_status "Checking JWT secret key..."
    
    if grep -q "your_secret_key_for_jwt_tokens_here" .env 2>/dev/null; then
        print_status "Generating new JWT secret key..."
        
        if command -v openssl &> /dev/null; then
            NEW_SECRET=$(openssl rand -hex 32)
            sed -i.bak "s/your_secret_key_for_jwt_tokens_here/$NEW_SECRET/" .env
            print_success "JWT secret key generated and updated in .env"
        else
            print_warning "OpenSSL not found. Please manually generate a secret key for SECRET_KEY"
        fi
    fi
}

# Pull Docker images
pull_images() {
    print_status "Pulling Docker images..."
    
    $DOCKER_COMPOSE_CMD -f infra/video-platform-dev.docker-compose.yml pull
    
    print_success "Docker images pulled"
}

# Build custom images
build_images() {
    print_status "Building custom Docker images..."
    
    $DOCKER_COMPOSE_CMD -f infra/video-platform-dev.docker-compose.yml build
    
    print_success "Custom Docker images built"
}

# Start services
start_services() {
    print_status "Starting video platform services..."
    
    $DOCKER_COMPOSE_CMD -f infra/video-platform-dev.docker-compose.yml up -d
    
    print_success "Services started"
}

# Wait for services to be ready
wait_for_services() {
    print_status "Waiting for services to be ready..."
    
    # Wait for database
    print_status "Waiting for PostgreSQL..."
    timeout 60 bash -c 'until docker exec meatlizard-video-db pg_isready -U postgres; do sleep 2; done'
    
    # Wait for Redis
    print_status "Waiting for Redis..."
    timeout 30 bash -c 'until docker exec meatlizard-redis-master redis-cli ping | grep -q PONG; do sleep 2; done'
    
    # Wait for MinIO
    print_status "Waiting for MinIO..."
    timeout 60 bash -c 'until curl -f http://localhost:9000/minio/health/live &>/dev/null; do sleep 2; done'
    
    # Wait for web service
    print_status "Waiting for web service..."
    timeout 60 bash -c 'until curl -f http://localhost:8000/health &>/dev/null; do sleep 2; done'
    
    print_success "All services are ready"
}

# Run database migrations
run_migrations() {
    print_status "Running database migrations..."
    
    # Check if alembic is available in the web container
    if docker exec meatlizard-video-web which alembic &>/dev/null; then
        docker exec meatlizard-video-web alembic upgrade head
        print_success "Database migrations completed"
    else
        print_warning "Alembic not found in web container. Please run migrations manually."
    fi
}

# Create initial database indexes
create_indexes() {
    print_status "Creating video platform database indexes..."
    
    docker exec meatlizard-video-db psql -U postgres -d meatlizard_video -c "SELECT create_video_platform_indexes();" || true
    
    print_success "Database indexes created"
}

# Show service status
show_status() {
    print_status "Service Status:"
    echo ""
    
    $DOCKER_COMPOSE_CMD -f infra/video-platform-dev.docker-compose.yml ps
    
    echo ""
    print_success "Video Platform Development Environment is ready!"
    echo ""
    echo "🌐 Web Interface: http://localhost:8000"
    echo "📊 Grafana Dashboard: http://localhost:3000 (admin/admin)"
    echo "📈 Prometheus: http://localhost:9090"
    echo "💾 MinIO Console: http://localhost:9001 (minioadmin/minioadmin123)"
    echo "🗄️  PostgreSQL: localhost:5432 (postgres/video_platform_dev_password_2024)"
    echo "🔄 Redis: localhost:6379"
    echo ""
    echo "📝 Logs: $DOCKER_COMPOSE_CMD -f infra/video-platform-dev.docker-compose.yml logs -f [service]"
    echo "🛑 Stop: $DOCKER_COMPOSE_CMD -f infra/video-platform-dev.docker-compose.yml down"
    echo ""
}

# Main execution
main() {
    echo "🎬 Video Platform Development Environment Setup"
    echo "=============================================="
    echo ""
    
    check_docker
    check_docker_compose
    create_directories
    setup_environment
    generate_encryption_key
    generate_jwt_secret
    pull_images
    build_images
    start_services
    wait_for_services
    run_migrations
    create_indexes
    show_status
    
    print_success "Setup completed successfully! 🎉"
}

# Run main function
main "$@"