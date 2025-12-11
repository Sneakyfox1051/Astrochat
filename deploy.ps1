# AstroRemedis AWS Deployment Script (PowerShell)
# This script helps deploy the backend to AWS on Windows

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("eb", "apprunner", "ecs")]
    [string]$DeploymentType = "eb",
    
    [Parameter(Mandatory=$false)]
    [string]$Environment = "production",
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-east-1"
)

Write-Host "AstroRemedis AWS Deployment Script" -ForegroundColor Green
Write-Host "Deployment Type: $DeploymentType"
Write-Host "Environment: $Environment"
Write-Host "Region: $Region"
Write-Host ""

# Check prerequisites
function Check-Prerequisites {
    Write-Host "Checking prerequisites..." -ForegroundColor Yellow
    
    if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
        Write-Host "AWS CLI is not installed. Please install it first." -ForegroundColor Red
        exit 1
    }
    
    try {
        aws sts get-caller-identity | Out-Null
    } catch {
        Write-Host "AWS credentials not configured. Run 'aws configure' first." -ForegroundColor Red
        exit 1
    }
    
    Write-Host "✓ Prerequisites check passed" -ForegroundColor Green
}

# Deploy to App Runner
function Deploy-AppRunner {
    Write-Host "Deploying to App Runner..." -ForegroundColor Yellow
    
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "Docker is not installed. Please install it first." -ForegroundColor Red
        exit 1
    }
    
    # Get AWS account ID
    $AccountId = (aws sts get-caller-identity --query Account --output text)
    $EcrRepo = "$AccountId.dkr.ecr.$Region.amazonaws.com/astroremedis-backend"
    
    # Create ECR repository if it doesn't exist
    try {
        aws ecr describe-repositories --repository-names astroremedis-backend --region $Region 2>&1 | Out-Null
    } catch {
        Write-Host "Creating ECR repository..." -ForegroundColor Yellow
        aws ecr create-repository --repository-name astroremedis-backend --region $Region
    }
    
    # Login to ECR
    Write-Host "Logging in to ECR..." -ForegroundColor Yellow
    $LoginCommand = aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $EcrRepo
    Invoke-Expression $LoginCommand
    
    # Build and push image
    Write-Host "Building Docker image..." -ForegroundColor Yellow
    docker build -t astroremedis-backend .
    
    Write-Host "Tagging and pushing image..." -ForegroundColor Yellow
    docker tag astroremedis-backend:latest "$EcrRepo`:latest"
    docker push "$EcrRepo`:latest"
    
    Write-Host "✓ Image pushed to ECR" -ForegroundColor Green
    Write-Host "Next steps:"
    Write-Host "1. Go to AWS Console → App Runner"
    Write-Host "2. Create service from container image"
    Write-Host "3. Select: $EcrRepo`:latest"
    Write-Host "4. Configure environment variables and deploy"
}

# Deploy to ECS
function Deploy-ECS {
    Write-Host "Deploying to ECS..." -ForegroundColor Yellow
    
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "Docker is not installed. Please install it first." -ForegroundColor Red
        exit 1
    }
    
    # Get AWS account ID
    $AccountId = (aws sts get-caller-identity --query Account --output text)
    $EcrRepo = "$AccountId.dkr.ecr.$Region.amazonaws.com/astroremedis-backend"
    
    # Create ECR repository if it doesn't exist
    try {
        aws ecr describe-repositories --repository-names astroremedis-backend --region $Region 2>&1 | Out-Null
    } catch {
        Write-Host "Creating ECR repository..." -ForegroundColor Yellow
        aws ecr create-repository --repository-name astroremedis-backend --region $Region
    }
    
    # Login to ECR
    Write-Host "Logging in to ECR..." -ForegroundColor Yellow
    $LoginCommand = aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $EcrRepo
    Invoke-Expression $LoginCommand
    
    # Build and push image
    Write-Host "Building Docker image..." -ForegroundColor Yellow
    docker build -t astroremedis-backend .
    
    Write-Host "Tagging and pushing image..." -ForegroundColor Yellow
    docker tag astroremedis-backend:latest "$EcrRepo`:latest"
    docker push "$EcrRepo`:latest"
    
    Write-Host "✓ Image pushed to ECR" -ForegroundColor Green
    Write-Host "Next steps:"
    Write-Host "1. Create ECS cluster, task definition, and service"
    Write-Host "2. Use image: $EcrRepo`:latest"
    Write-Host "3. Configure environment variables and deploy"
}

# Main deployment logic
Check-Prerequisites

switch ($DeploymentType) {
    "apprunner" {
        Deploy-AppRunner
    }
    "ecs" {
        Deploy-ECS
    }
    "eb" {
        Write-Host "For Elastic Beanstalk, use the EB CLI:" -ForegroundColor Yellow
        Write-Host "  eb init -p python-3.11 astroremedis-backend --region $Region"
        Write-Host "  eb create $Environment --instance-type t3.small"
        Write-Host "  eb deploy $Environment"
    }
    default {
        Write-Host "Invalid deployment type: $DeploymentType" -ForegroundColor Red
        Write-Host "Usage: .\deploy.ps1 -DeploymentType [eb|apprunner|ecs] -Environment [environment] -Region [region]"
        exit 1
    }
}

