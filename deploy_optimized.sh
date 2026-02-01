#!/bin/bash

# Voice Perception System Optimization Deployment Script
# This script automates the deployment of optimized components

set -e

echo "================================"
echo "Voice Perception Optimization"
echo "Deployment Script v2.0"
echo "================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
OPTIMIZED_DIR="./optimized"

# Create backup directory
mkdir -p "$BACKUP_DIR"
mkdir -p "$OPTIMIZED_DIR"

echo ""
echo -e "${GREEN}[1/8] Checking prerequisites...${NC}"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

# Check if PostgreSQL client is installed
if ! command -v psql &> /dev/null; then
    echo -e "${YELLOW}Warning: PostgreSQL client not found. Database optimization will be skipped.${NC}"
    SKIP_DB=true
else
    SKIP_DB=false
fi

echo -e "${GREEN}Prerequisites check passed${NC}"

echo ""
echo -e "${GREEN}[2/8] Backing up original files...${NC}"

# Backup original files
FILES_TO_BACKUP=(
    "transcript_server/tr_lib.py"
    "transcript_server/transcript.py"
    "text_processor/textprocessor.py"
    "tag_server/tagserver.py"
)

for file in "${FILES_TO_BACKUP[@]}"; do
    if [ -f "$file" ]; then
        cp "$file" "$BACKUP_DIR/"
        echo -e "${GREEN}Backed up: $file${NC}"
    else
        echo -e "${YELLOW}Warning: $file not found${NC}"
    fi
done

echo -e "${GREEN}Backup completed. Files saved to: $BACKUP_DIR${NC}"

echo ""
echo -e "${GREEN}[3/8] Applying database optimizations...${NC}"

if [ "$SKIP_DB" = false ]; then
    if [ -f "database_optimization.sql" ]; then
        # Read DSN from environment or use default
        DSN=${DSN:-"postgresql://postgres:postgres@localhost:5432/videoleti"}
        
        echo "Applying database optimizations..."
        psql "$DSN" -f database_optimization.sql
        echo -e "${GREEN}Database optimization completed${NC}"
    else
        echo -e "${YELLOW}Warning: database_optimization.sql not found${NC}"
    fi
else
    echo -e "${YELLOW}Skipped database optimization (psql not available)${NC}"
fi

echo ""
echo -e "${GREEN}[4/8] Checking environment variables...${NC}"

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    if [ -f ".env.example" ]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
        echo -e "${YELLOW}Please edit .env with your configuration${NC}"
    fi
else
    echo -e "${GREEN}.env file found${NC}"
fi

echo ""
echo -e "${GREEN}[5/8] Deploying optimized files...${NC}"

# Deploy optimized files
DEPLOY_MAP=(
    "transcript_server/tr_lib_optimized.py:transcript_server/tr_lib.py"
    "transcript_server/transcript_optimized.py:transcript_server/transcript.py"
    "text_processor/textprocessor_optimized.py:text_processor/textprocessor.py"
    "tag_server/tagserver_optimized.py:tag_server/tagserver.py"
)

for mapping in "${DEPLOY_MAP[@]}"; do
    IFS=':' read -r src dest <<< "$mapping"
    
    if [ -f "$src" ]; then
        cp "$src" "$dest"
        echo -e "${GREEN}Deployed: $src -> $dest${NC}"
    else
        echo -e "${RED}Error: Optimized file not found: $src${NC}"
        exit 1
    fi
done

echo -e "${GREEN}All optimized files deployed${NC}"

echo ""
echo -e "${GREEN}[6/8] Creating required directories...${NC}"

# Create cache directory if not exists
CACHE_DIR=${CACHE_DIR:-"./cache"}
mkdir -p "$CACHE_DIR"
echo -e "${GREEN}Created cache directory: $CACHE_DIR${NC}"

# Create temp media directory if not exists
TEMP_DIR=${TEMP_DIR:-"./tempmedia"}
mkdir -p "$TEMP_DIR"
echo -e "${GREEN}Created temp directory: $TEMP_DIR${NC}"

echo ""
echo -e "${GREEN}[7/8] Installing dependencies (if needed)...${NC}"

# Check if requirements files exist
if [ -f "requirements.txt" ]; then
    echo "Installing/updating Python dependencies..."
    pip install -q -r requirements.txt || echo -e "${YELLOW}Warning: Some dependencies may have failed${NC}"
else
    echo -e "${YELLOW}requirements.txt not found, skipping dependency installation${NC}"
fi

echo ""
echo -e "${GREEN}[8/8] Checking running services...${NC}"

# Check if services are running
SERVICES=("transcript" "textprocessor" "tagserver")

for service in "${SERVICES[@]}"; do
    if pgrep -f "$service" > /dev/null; then
        echo -e "${YELLOW}Service $service is running${NC}"
        echo "To restart with optimized version, run:"
        echo "  pkill -f $service"
        echo "  python ${service}_server/transcript.py &"
    else
        echo -e "${GREEN}Service $service is not running${NC}"
    fi
done

echo ""
echo "================================"
echo -e "${GREEN}Deployment completed successfully!${NC}"
echo "================================"
echo ""
echo "Summary:"
echo "  - Original files backed up to: $BACKUP_DIR"
echo "  - Database optimizations applied"
echo "  - Optimized files deployed"
echo "  - Required directories created"
echo ""
echo "Next steps:"
echo "  1. Review and update .env configuration"
echo "  2. Restart services to use optimized code:"
echo "     pkill -f transcript && python transcript_server/transcript.py &"
echo "     pkill -f textprocessor && python text_processor/textprocessor.py &"
echo "     pkill -f tagserver && python tag_server/tagserver.py &"
echo "  3. Monitor logs and performance metrics"
echo "  4. Refer to OPTIMIZATION_GUIDE.md for details"
echo ""
echo "To rollback:"
echo "  cp $BACKUP_DIR/* ."
echo ""
echo "================================"