#!/bin/bash

# MeatLizard AI Platform Status Check Script
# Comprehensive health check for all services

set -e

echo "🦎 MeatLizard AI Platform - Status Check"
echo "========================================"
echo "Timestamp: $(date)"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    local service=$1
    local status=$2
    local details=$3
    
    if [ "$status" = "OK" ]; then
        echo -e "✅ ${GREEN}$service${NC}: $details"
    elif [ "$status" = "WARNING" ]; then
        echo -e "⚠️  ${YELLOW}$service${NC}: $details"
    else
        echo -e "❌ ${RED}$service${NC}: $details"
    fi
}

# Check if Docker is running
echo "🐳 Docker Services"
echo "=================="

if ! docker info > /dev/null 2>&1; then
    print_status "Docker" "ERROR" "Docker is not running"
    exit 1
else
    print_status "Docker" "OK" "Docker is running"
fi

# Check Docker Compose services
if [ -f "docker-compose.yml" ]; then
    echo ""
    echo "📦 Container Status"
    echo "=================="
    
    services=("postgres" "redis" "web" "server_bot" "transcoding_worker" "import_worker")
    
    for service in "${services[@]}"; do
        if docker-compose ps $service | grep -q "Up\|healthy"; then
            uptime=$(docker-compose ps $service | grep "Up" | awk '{for(i=4;i<=NF;i++) printf "%s ", $i; print ""}' | sed 's/Up //')
            print_status "$service" "OK" "Running ($uptime)"
        else
            print_status "$service" "ERROR" "Not running or unhealthy"
        fi
    done
else
    print_status "Docker Compose" "ERROR" "docker-compose.yml not found"
fi

# Check database connectivity
echo ""
echo "🗄️  Database Status"
echo "=================="

if docker-compose exec -T postgres pg_isready -U meatlizard > /dev/null 2>&1; then
    # Get database stats
    db_size=$(docker-compose exec -T postgres psql -U meatlizard -d meatlizard -t -c "SELECT pg_size_pretty(pg_database_size('meatlizard'));" 2>/dev/null | xargs)
    connection_count=$(docker-compose exec -T postgres psql -U meatlizard -d meatlizard -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname='meatlizard';" 2>/dev/null | xargs)
    print_status "PostgreSQL" "OK" "Connected (Size: $db_size, Connections: $connection_count)"
else
    print_status "PostgreSQL" "ERROR" "Cannot connect to database"
fi

# Check Redis connectivity
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    memory_usage=$(docker-compose exec -T redis redis-cli info memory | grep "used_memory_human" | cut -d: -f2 | tr -d '\r')
    print_status "Redis" "OK" "Connected (Memory: $memory_usage)"
else
    print_status "Redis" "ERROR" "Cannot connect to Redis"
fi

# Check web service health
echo ""
echo "🌐 Web Service Status"
echo "===================="

if curl -f -s http://localhost:8000/health > /dev/null 2>&1; then
    response=$(curl -s http://localhost:8000/health)
    print_status "Web API" "OK" "Health endpoint responding"
    
    # Check if authentication is working
    if curl -f -s http://localhost:8000/api/auth/me > /dev/null 2>&1; then
        print_status "Authentication" "OK" "Auth endpoints accessible"
    else
        print_status "Authentication" "WARNING" "Auth endpoints may require token"
    fi
else
    print_status "Web API" "ERROR" "Health endpoint not responding"
fi

# Check Discord bot status
echo ""
echo "🤖 Discord Bot Status"
echo "===================="

# Check if server bot is connected (look for recent logs)
if docker-compose logs --tail=50 server_bot 2>/dev/null | grep -q "Bot logged in\|ready"; then
    print_status "Server Bot" "OK" "Connected to Discord"
else
    print_status "Server Bot" "WARNING" "May not be connected to Discord"
fi

# Check for client bot activity (if logs exist)
if [ -f "client_bot/logs/client_bot.log" ]; then
    if tail -50 client_bot/logs/client_bot.log 2>/dev/null | grep -q "Client Bot logged in\|ready"; then
        print_status "Client Bot" "OK" "Connected to Discord"
    else
        print_status "Client Bot" "WARNING" "May not be connected to Discord"
    fi
else
    print_status "Client Bot" "WARNING" "No client bot logs found (may be running on different machine)"
fi

# Check storage and disk space
echo ""
echo "💾 Storage Status"
echo "================"

# Check disk space
disk_usage=$(df -h . | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$disk_usage" -gt 90 ]; then
    print_status "Disk Space" "ERROR" "${disk_usage}% used - critically low"
elif [ "$disk_usage" -gt 80 ]; then
    print_status "Disk Space" "WARNING" "${disk_usage}% used - getting low"
else
    print_status "Disk Space" "OK" "${disk_usage}% used"
fi

# Check media directory
if [ -d "media" ]; then
    media_size=$(du -sh media 2>/dev/null | cut -f1)
    print_status "Media Storage" "OK" "Directory exists ($media_size)"
else
    print_status "Media Storage" "WARNING" "Media directory not found"
fi

# Check logs directory
if [ -d "logs" ]; then
    log_size=$(du -sh logs 2>/dev/null | cut -f1)
    print_status "Logs" "OK" "Directory exists ($log_size)"
else
    print_status "Logs" "WARNING" "Logs directory not found"
fi

# Check system resources
echo ""
echo "⚡ System Resources"
echo "=================="

# Memory usage
if command -v free > /dev/null 2>&1; then
    memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    if (( $(echo "$memory_usage > 90" | bc -l) )); then
        print_status "Memory" "ERROR" "${memory_usage}% used - critically high"
    elif (( $(echo "$memory_usage > 80" | bc -l) )); then
        print_status "Memory" "WARNING" "${memory_usage}% used - getting high"
    else
        print_status "Memory" "OK" "${memory_usage}% used"
    fi
fi

# CPU load
if command -v uptime > /dev/null 2>&1; then
    load_avg=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
    cpu_cores=$(nproc 2>/dev/null || echo "1")
    load_percent=$(echo "scale=1; $load_avg / $cpu_cores * 100" | bc -l 2>/dev/null || echo "0")
    
    if (( $(echo "$load_percent > 90" | bc -l) )); then
        print_status "CPU Load" "ERROR" "${load_percent}% (${load_avg} avg)"
    elif (( $(echo "$load_percent > 70" | bc -l) )); then
        print_status "CPU Load" "WARNING" "${load_percent}% (${load_avg} avg)"
    else
        print_status "CPU Load" "OK" "${load_percent}% (${load_avg} avg)"
    fi
fi

# Check network connectivity
echo ""
echo "🌐 Network Status"
echo "================"

# Check internet connectivity
if ping -c 1 8.8.8.8 > /dev/null 2>&1; then
    print_status "Internet" "OK" "Connected"
else
    print_status "Internet" "ERROR" "No internet connectivity"
fi

# Check Discord API connectivity
if curl -f -s https://discord.com/api/v10/gateway > /dev/null 2>&1; then
    print_status "Discord API" "OK" "Reachable"
else
    print_status "Discord API" "ERROR" "Cannot reach Discord API"
fi

# Check recent errors in logs
echo ""
echo "🚨 Recent Errors"
echo "================"

error_count=0

# Check web service errors
if docker-compose logs --tail=100 web 2>/dev/null | grep -i "error\|exception\|failed" | head -5 | while read line; do
    echo "   Web: $line"
    ((error_count++))
done

# Check server bot errors
if docker-compose logs --tail=100 server_bot 2>/dev/null | grep -i "error\|exception\|failed" | head -5 | while read line; do
    echo "   Server Bot: $line"
    ((error_count++))
done

# Check client bot errors (if logs exist)
if [ -f "client_bot/logs/client_bot_error.log" ]; then
    if tail -100 client_bot/logs/client_bot_error.log 2>/dev/null | grep -i "error\|exception\|failed" | head -5 | while read line; do
        echo "   Client Bot: $line"
        ((error_count++))
    done
fi

if [ $error_count -eq 0 ]; then
    print_status "Recent Errors" "OK" "No recent errors found"
fi

# Performance metrics
echo ""
echo "📊 Performance Metrics"
echo "====================="

# Database performance
if docker-compose exec -T postgres psql -U meatlizard -d meatlizard -c "SELECT count(*) as total_sessions FROM ai_chat_sessions;" 2>/dev/null | grep -q "[0-9]"; then
    session_count=$(docker-compose exec -T postgres psql -U meatlizard -d meatlizard -t -c "SELECT count(*) FROM ai_chat_sessions;" 2>/dev/null | xargs)
    active_sessions=$(docker-compose exec -T postgres psql -U meatlizard -d meatlizard -t -c "SELECT count(*) FROM ai_chat_sessions WHERE ended_at IS NULL;" 2>/dev/null | xargs)
    print_status "AI Sessions" "OK" "Total: $session_count, Active: $active_sessions"
fi

# Check uptime
if command -v uptime > /dev/null 2>&1; then
    system_uptime=$(uptime -p 2>/dev/null || uptime | awk '{print $3,$4}')
    print_status "System Uptime" "OK" "$system_uptime"
fi

# Summary
echo ""
echo "📋 Summary"
echo "=========="

# Count services
total_services=0
healthy_services=0

# This is a simplified count - in a real implementation, you'd track the actual status
echo "Service health summary would be calculated here based on the checks above."

echo ""
echo "🔧 Useful Commands"
echo "=================="
echo "View logs:           docker-compose logs -f [service]"
echo "Restart service:     docker-compose restart [service]"
echo "Check client bot:    cd client_bot && ./monitor_client_bot.sh"
echo "Database backup:     scripts/backup-database.sh"
echo "Full restart:        docker-compose down && docker-compose up -d"
echo ""
echo "Status check completed at $(date)"