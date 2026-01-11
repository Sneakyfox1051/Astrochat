#!/bin/bash

# AstroRemedis AWS Deployment Script
# This script helps deploy the backend to AWS

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DEPLOYMENT_TYPE="${1:-eb}"  # eb, apprunner, or ecs
ENVIRONMENT="${2:-production}"
REGION="${3:-us-east-1}"

echo -e "${GREEN}AstroRemedis AWS Deployment Script${NC}"
echo "Deployment Type: $DEPLOYMENT_TYPE"
echo "Environment: $ENVIRONMENT"
echo "Region: $REGION"
echo ""

# Check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"
    
    if ! command -v aws &> /dev/null; then
        echo -e "${RED}AWS CLI is not installed. Please install it first.${NC}"
        exit 1
    fi
    
    if ! aws sts get-caller-identity &> /dev/null; then
        echo -e "${RED}AWS credentials not configured. Run 'aws configure' first.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Prerequisites check passed${NC}"
}

# Deploy to Elastic Beanstalk
deploy_eb() {
    echo -e "${YELLOW}Deploying to Elastic Beanstalk...${NC}"
    
    if ! command -v eb &> /dev/null; then
        echo -e "${YELLOW}EB CLI not found. Installing...${NC}"
        pip install awsebcli
    fi
    
    # Check if already initialized
    if [ ! -f ".elasticbeanstalk/config.yml" ]; then
        echo -e "${YELLOW}Initializing Elastic Beanstalk...${NC}"
        eb init -p python-3.11 astroremedis-backend --region $REGION
    fi
    
    # Create environment if it doesn't exist
    if ! eb list | grep -q "$ENVIRONMENT"; then
        echo -e "${YELLOW}Creating new environment: $ENVIRONMENT${NC}"
        eb create $ENVIRONMENT --instance-type t3.small --min-size 1 --max-size 3
    fi
    
    # Deploy
    echo -e "${YELLOW}Deploying application...${NC}"
    eb deploy $ENVIRONMENT
    
    echo -e "${GREEN}✓ Deployment complete!${NC}"
    echo "Get your URL: eb status"
}

# Deploy to App Runner
deploy_apprunner() {
    echo -e "${YELLOW}Deploying to App Runner...${NC}"
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Docker is not installed. Please install it first.${NC}"
        exit 1
    fi
    
    # Get AWS account ID
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    ECR_REPO="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/astroremedis-backend"
    
    # Create ECR repository if it doesn't exist
    if ! aws ecr describe-repositories --repository-names astroremedis-backend --region $REGION &> /dev/null; then
        echo -e "${YELLOW}Creating ECR repository...${NC}"
        aws ecr create-repository --repository-name astroremedis-backend --region $REGION
    fi
    
    # Login to ECR
    echo -e "${YELLOW}Logging in to ECR...${NC}"
    aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_REPO
    
    # Build and push image
    echo -e "${YELLOW}Building Docker image...${NC}"
    docker build -t astroremedis-backend .
    
    echo -e "${YELLOW}Tagging and pushing image...${NC}"
    docker tag astroremedis-backend:latest $ECR_REPO:latest
    docker push $ECR_REPO:latest
    
    echo -e "${GREEN}✓ Image pushed to ECR${NC}"
    echo "Next steps:"
    echo "1. Go to AWS Console → App Runner"
    echo "2. Create service from container image"
    echo "3. Select: $ECR_REPO:latest"
    echo "4. Configure environment variables and deploy"
}

# Deploy to ECS
deploy_ecs() {
    echo -e "${YELLOW}Deploying to ECS...${NC}"
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Docker is not installed. Please install it first.${NC}"
        exit 1
    fi
    
    # Get AWS account ID
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    ECR_REPO="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/astroremedis-backend"
    
    # Create ECR repository if it doesn't exist
    if ! aws ecr describe-repositories --repository-names astroremedis-backend --region $REGION &> /dev/null; then
        echo -e "${YELLOW}Creating ECR repository...${NC}"
        aws ecr create-repository --repository-name astroremedis-backend --region $REGION
    fi
    
    # Login to ECR
    echo -e "${YELLOW}Logging in to ECR...${NC}"
    aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_REPO
    
    # Build and push image
    echo -e "${YELLOW}Building Docker image...${NC}"
    docker build -t astroremedis-backend .
    
    echo -e "${YELLOW}Tagging and pushing image...${NC}"
    docker tag astroremedis-backend:latest $ECR_REPO:latest
    docker push $ECR_REPO:latest
    
    echo -e "${GREEN}✓ Image pushed to ECR${NC}"
    echo "Next steps:"
    echo "1. Create ECS cluster, task definition, and service"
    echo "2. Use image: $ECR_REPO:latest"
    echo "3. Configure environment variables and deploy"
}

# Main deployment logic
main() {
    check_prerequisites
    
    case $DEPLOYMENT_TYPE in
        eb)
            deploy_eb
            ;;
        apprunner)
            deploy_apprunner
            ;;
        ecs)
            deploy_ecs
            ;;
        *)
            echo -e "${RED}Invalid deployment type: $DEPLOYMENT_TYPE${NC}"
            echo "Usage: $0 [eb|apprunner|ecs] [environment] [region]"
            exit 1
            ;;
    esac
}

main








