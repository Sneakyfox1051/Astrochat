# AstroRemedis Backend API

A sophisticated astrology chatbot backend that provides AI-powered consultations, Kundli chart generation, and spiritual guidance using advanced technologies.

## 🌟 Features

- **AI-Powered Astrology**: GPT-4 powered consultations with spiritual Pandit Ji persona
- **Kundli Chart Generation**: Real-time chart generation via ProKerala API
- **RAG (Retrieval Augmented Generation)**: Enhanced responses using KP astrology knowledge base
- **Google Sheets Integration**: Automatic form data storage using Service Account authentication
- **Realistic Predictions**: Age-appropriate and logical astrological predictions
- **Spiritual Communication**: Warm, empathetic, and spiritually engaging responses

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Google Cloud Service Account
- ProKerala API credentials
- OpenAI API key

### Installation

1. **Clone and navigate to backend directory**
   ```bash
   cd backend
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp env_example.txt .env
   # Edit .env with your actual credentials
   ```

4. **Run the server**
   ```bash
   python app.py
   ```

The server will start on `http://localhost:5000`

## 📋 Environment Configuration

Create a `.env` file in the backend directory with the following variables:

### Required Variables

```env
# ProKerala API (for Kundli generation)
PROKERALA_CLIENT_ID=your_prokerala_client_id
PROKERALA_CLIENT_SECRET=your_prokerala_client_secret

# OpenAI API (for AI consultations)
OPENAI_API_KEY=your_openai_api_key

# Google Sheets Service Account (preferred method)
GOOGLE_SERVICE_ACCOUNT_FILE=path/to/service-account.json
# OR
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}

# Target Google Sheet
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id
```

### Optional Variables

```env
# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True

# Google Sheets naming
GOOGLE_SHEETS_SPREADSHEET_NAME=AstroRemedis Data
GOOGLE_SHEETS_WORKSHEET_NAME=Sheet1
```

## 🔧 Google Sheets Setup

### Method 1: Service Account (Recommended)

1. **Create Service Account**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing
   - Enable Google Sheets API
   - Create Service Account → Download JSON key

2. **Share Spreadsheet**
   - Open your target Google Sheet
   - Share with service account email (ends with `@project.iam.gserviceaccount.com`)
   - Grant Editor permissions

3. **Configure Environment**
   ```env
   GOOGLE_SERVICE_ACCOUNT_FILE=D:/path/to/service-account.json
   GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id
   ```

### Method 2: OAuth (Alternative)

If you prefer OAuth over Service Account:

```env
GOOGLE_CLIENT_ID=your_oauth_client_id
GOOGLE_CLIENT_SECRET=your_oauth_client_secret
GOOGLE_REFRESH_TOKEN=your_refresh_token
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id
```

## 📚 API Endpoints

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API status and available endpoints |
| `/api/health` | GET | Health check with feature status |
| `/api/chat` | POST | AI-powered astrology chat |
| `/api/kundli` | POST | Generate comprehensive Kundli data |
| `/api/chart` | POST | Generate visual Kundli chart |
| `/api/analyze` | POST | Analyze Kundli using RAG |
| `/api/form-submit` | POST | Submit form data to Google Sheets |
| `/api/sheets/diagnose` | GET | Diagnose Google Sheets connection |

### Example API Calls

**Generate Kundli:**
```bash
curl -X POST http://localhost:5000/api/kundli \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Rajesh Kumar",
    "dob": "1990-05-15",
    "tob": "14:30:00",
    "place": "Delhi",
    "timezone": "Asia/Kolkata"
  }'
```

**Chat with AI:**
```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "When will I get married?",
    "chart_data": {...}
  }'
```

## 🏗️ Architecture

### Core Components

1. **EnhancedAstroBotAPI Class**
   - Manages ProKerala API authentication
   - Handles Kundli chart generation
   - Implements RAG with KP astrology rules
   - Provides AI-powered consultations

2. **Google Sheets Integration**
   - Service Account authentication
   - Form data storage
   - Connection diagnostics

3. **RAG System**
   - Loads KP astrology documents
   - Creates vector embeddings
   - Retrieves relevant context for AI responses

### Data Flow

```
User Form → Backend API → ProKerala API → Kundli Data
                ↓
         Google Sheets Storage
                ↓
         AI Chat with RAG → OpenAI GPT-4 → Spiritual Response
```

## 🔍 Diagnostics

### Check Google Sheets Connection

```bash
curl http://localhost:5000/api/sheets/diagnose
```

Expected response:
```json
{
  "ok": true,
  "spreadsheet_id": "1E0u7Ds-hhDHq1MaiAM4BMYNhN30AndyL4S2_AaClAAE",
  "title": "AstroRemedis Data",
  "sheets": ["Sheet1"],
  "presence": {
    "SERVICE_ACCOUNT_FILE": true,
    "GOOGLE_SHEETS_SPREADSHEET_ID": true
  }
}
```

### Health Check

```bash
curl http://localhost:5000/api/health
```

## 🛠️ Development

### Project Structure

```
backend/
├── app.py                 # Main Flask application
├── google_sheets.py       # Google Sheets integration
├── requirements.txt       # Python dependencies
├── env_example.txt        # Environment variables template
├── start_server.py        # Server startup script
├── test_api.py           # API testing utilities
└── README.md             # This file
```

### Key Features Implementation

- **Spiritual AI Responses**: Enhanced system prompt for warm, empathetic communication
- **Realistic Predictions**: Age validation and logical timeline predictions
- **8-10 Second Delays**: Thoughtful pauses for prediction responses
- **Automatic Remedies**: AI provides upchar (remedies) with every prediction
- **Service Account Auth**: Secure, no-refresh-token authentication

## 🐛 Troubleshooting

### Common Issues

1. **Google Sheets Connection Failed**
   - Verify service account JSON file path
   - Ensure spreadsheet is shared with service account email
   - Check `GOOGLE_SHEETS_SPREADSHEET_ID` is correct

2. **ProKerala API Errors**
   - Verify `PROKERALA_CLIENT_ID` and `PROKERALA_CLIENT_SECRET`
   - Check API quota and billing status

3. **OpenAI API Issues**
   - Verify `OPENAI_API_KEY` is valid
   - Check API usage limits

4. **Import Errors**
   - Ensure all dependencies are installed: `pip install -r requirements.txt`
   - Check Python version compatibility

### Debug Mode

Enable debug logging:
```env
FLASK_DEBUG=True
FLASK_ENV=development
```

## 📄 License

This project is proprietary software developed for AstroRemedis.

## 🤝 Support

For technical support or questions, contact the AstroRemedis development team.

---

**Version**: 2.0.0  
**Last Updated**: 2024  
**Author**: AstroRemedis Development Team