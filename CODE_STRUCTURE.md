# AstroRemedis Code Structure

## Overview

This document describes the overall structure and organization of the AstroRemedis codebase.

## Project Structure

```
astro-main/
├── backend/                 # Python Flask backend
│   ├── app.py              # Main Flask application (all routes and logic)
│   ├── config.py           # Configuration constants (follow-up questions, etc.)
│   ├── google_sheets.py    # Google Sheets integration (optional)
│   └── README.md           # Backend documentation
│
├── frontend/                # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   │   ├── AstroBotUI.js          # Main app component
│   │   │   ├── ExpandableChat.js      # Chat interface
│   │   │   ├── UserDataForm.js        # Birth details form
│   │   │   ├── KundliChart.js         # Chart display
│   │   │   ├── FeedbackModal.js       # Feedback collection
│   │   │   ├── BottomNavigation.js    # Navigation controls
│   │   │   ├── Character.js           # Character image
│   │   │   ├── ChatBubble.js          # Greeting bubble
│   │   │   └── ErrorBoundary.js       # Error handling
│   │   ├── services/
│   │   │   └── api.js                 # API service layer
│   │   ├── utils/
│   │   │   ├── logger.js              # Logging utility
│   │   │   ├── sanitize.js            # Input sanitization
│   │   │   └── storage.js             # localStorage utility
│   │   ├── data/
│   │   │   └── indianCities.js        # City data
│   │   └── index.js                   # React entry point
│   └── package.json
│
├── wsgi.py                  # WSGI entry point for AWS deployment
├── Procfile                 # Gunicorn configuration for production
├── requirements.txt         # Python dependencies
├── Dockerfile               # Docker configuration
├── .ebextensions/          # Elastic Beanstalk configuration
├── deploy.sh               # Deployment script (Linux/Mac)
├── deploy.ps1              # Deployment script (Windows)
├── DEPLOYMENT.md           # Deployment documentation
└── README.md               # Project README
```

## Backend Architecture

### Main Components

1. **Flask Application (`backend/app.py`)**
   - All API routes and endpoints
   - EnhancedAstroBotAPI class for external API integration
   - Thread management for conversation context
   - Chart data caching and request deduplication

2. **Configuration (`backend/config.py`)**
   - Follow-up questions by category
   - Response style mappings
   - Question introduction templates

3. **Google Sheets Integration (`backend/google_sheets.py`)**
   - Optional integration for storing form submissions and feedback
   - Uses OAuth2 for authentication

### Key Features

- **ProKerala API Integration**: 14 endpoints for comprehensive astrological data
- **OpenAI Assistant API**: AI-powered predictions and consultations
- **Connection Pooling**: Optimized HTTP sessions for parallel API calls
- **Caching**: LRU cache for chart data and geocoding results
- **Request Deduplication**: Prevents duplicate concurrent requests
- **Thread Management**: Maintains conversation context across requests

## Frontend Architecture

### Component Hierarchy

```
AstroBotUI (Root)
├── Character (Character image)
├── ChatBubble (Greeting)
├── BottomNavigation (Controls)
├── UserDataForm (Modal - Birth details)
└── ExpandableChat (Main chat interface)
    ├── KundliChart (Chart display)
    └── FeedbackModal (Feedback collection)
```

### Key Components

1. **AstroBotUI.js**: Main application component, manages state and component coordination
2. **ExpandableChat.js**: Chat interface with message handling and Kundli generation
3. **UserDataForm.js**: Modal form for collecting birth details
4. **KundliChart.js**: Displays SVG charts from ProKerala API
5. **api.js**: Centralized API service with error handling and retry logic

### Utilities

- **logger.js**: Centralized logging (dev-only in production)
- **sanitize.js**: Input sanitization for XSS protection
- **storage.js**: Safe localStorage operations with error handling

## Data Flow

### Kundli Generation Flow

1. User submits birth details via `UserDataForm`
2. Frontend calls `/api/kundli` endpoint
3. Backend:
   - Validates and geocodes place name
   - Fetches ProKerala access token
   - Makes 14 parallel API calls to ProKerala
   - Caches results
   - Returns chart data
4. Frontend displays chart in `KundliChart` component

### Chat Flow

1. User sends message via `ExpandableChat`
2. Frontend calls `/api/chat` with message and optional chart data
3. Backend:
   - Retrieves or creates OpenAI thread for conversation context
   - Calls OpenAI Assistant API with chart context
   - Returns AI response
4. Frontend displays response in chat interface

## Security Features

- **Input Sanitization**: All user inputs sanitized before processing
- **CORS Configuration**: Configurable allowed origins (restricted in production)
- **Security Headers**: X-Frame-Options, X-Content-Type-Options, etc.
- **Environment Variables**: Sensitive data stored in environment variables
- **HTTPS**: Enforced in production

## Performance Optimizations

- **Connection Pooling**: Reuses HTTP connections for faster API calls
- **Parallel API Calls**: Uses ThreadPoolExecutor for concurrent ProKerala requests
- **Caching**: LRU cache for chart data and geocoding
- **Request Deduplication**: Prevents duplicate concurrent requests
- **Code Splitting**: React components loaded on demand
- **Production Build**: Optimized with source maps disabled

## Deployment

- **Backend**: AWS (Elastic Beanstalk, App Runner, or ECS)
- **Frontend**: Static hosting (S3 + CloudFront, Netlify, Vercel, etc.)
- **WSGI Server**: Gunicorn (configured in Procfile)
- **Container Support**: Dockerfile for containerized deployments

## Code Quality

- **Comments**: All major functions and classes have docstrings
- **Error Handling**: Comprehensive try-catch blocks with logging
- **Type Hints**: Python type hints where applicable
- **Linting**: No linter errors
- **Unused Code**: Removed unused imports, functions, and constants

## Key Design Decisions

1. **RAG Pipeline Removed**: Using OpenAI Assistant API exclusively for better accuracy
2. **No Local AI**: All predictions handled by OpenAI (no local models)
3. **Thread-based Context**: Maintains conversation context via OpenAI threads
4. **Caching Strategy**: LRU cache with manual eviction for chart data
5. **Error Recovery**: Retry logic with exponential backoff for API calls
6. **Security First**: Input sanitization, CORS restrictions, security headers

## Future Improvements

- Consider adding Redis for distributed caching
- Add rate limiting for API endpoints
- Implement WebSocket support for real-time updates
- Add comprehensive unit and integration tests
- Consider GraphQL API for more flexible data fetching








