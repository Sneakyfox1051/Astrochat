# AWS Deployment Checklist

## ✅ Pre-Deployment Cleanup Completed

### Files Removed:
- ✅ `backend/test_credentials.py` - Test file removed
- ✅ `test_sheets.py` - Test file removed  
- ✅ `test-google-sheets.html` - Test file removed
- ✅ `test-iframe-embed.html` - Test file removed
- ✅ `__pycache__/` directories - Cleaned

### Security:
- ✅ `.gitignore` updated to exclude service account JSON files
- ✅ `.env` files are in `.gitignore` (already configured)
- ⚠️ **IMPORTANT**: Service account JSON file (`astroremedis-e082ee228a29.json`) should NOT be committed to git
- ⚠️ **IMPORTANT**: `.env` file should NOT be committed to git

## 📁 Project Structure

```
astro-main/
├── backend/                 # Backend application
│   ├── app.py              # Main Flask application
│   ├── config.py           # Configuration constants
│   ├── google_sheets.py    # Google Sheets integration
│   └── README.md           # Backend documentation
├── frontend/               # Frontend React application
│   ├── src/               # Source code
│   ├── public/            # Public assets
│   └── package.json       # Dependencies
├── wsgi.py                # WSGI entry point (for Gunicorn)
├── application.py         # Alternative WSGI entry (for EB)
├── Procfile               # Process file (for Heroku/EB)
├── requirements.txt       # Python dependencies
├── Dockerfile             # Docker configuration
└── .gitignore            # Git ignore rules
```

## 🚀 AWS Deployment Requirements

### 1. Environment Variables (Set in AWS Console)

**Required:**
- `OPENAI_API_KEY` - Your OpenAI API key
- `PROKERALA_CLIENT_ID` - ProKerala API client ID
- `PROKERALA_CLIENT_SECRET` - ProKerala API client secret
- `GOOGLE_SHEETS_SPREADSHEET_ID` - Your Google Sheet ID

**Google Sheets (Choose ONE method):**
- `GOOGLE_SERVICE_ACCOUNT_JSON` - Full JSON as string (recommended for AWS)
  OR
- `GOOGLE_SERVICE_ACCOUNT_FILE` - Path to JSON file (if uploaded to instance)

**Optional:**
- `GOOGLE_SHEETS_WORKSHEET_NAME` - Default: "Sheet1"
- `GOOGLE_SHEETS_SPREADSHEET_NAME` - Default: "AstroRemedis Data"
- `OPENAI_ASSISTANT_ID` - Default assistant ID
- `OPENAI_ASSISTANT_ID_HORARY` - Horary assistant ID
- `ALLOWED_ORIGINS` - CORS allowed origins (comma-separated)
- `FLASK_ENV` - Set to "production"
- `PORT` - Default: 8000

### 2. Google Service Account Setup

**Option A: JSON String (Recommended for AWS)**
1. Open your service account JSON file
2. Copy entire content as a single line (no line breaks)
3. Set `GOOGLE_SERVICE_ACCOUNT_JSON` environment variable in AWS
4. Remove all newlines and escape quotes properly

**Option B: Upload JSON File**
1. Upload `astroremedis-e082ee228a29.json` to your EC2 instance
2. Set `GOOGLE_SERVICE_ACCOUNT_FILE` to the full path
3. Ensure file has correct permissions (readable by app user)

### 3. Share Google Sheet
- Share your Google Sheet with: `astroremedis@astroremedis.iam.gserviceaccount.com`
- Give it **Editor** access

## 📦 Deployment Methods

### AWS Elastic Beanstalk
1. Use `Procfile` for process definition
2. `wsgi.py` or `application.py` as entry point
3. Set environment variables in EB Console
4. Deploy via EB CLI or Console

### AWS ECS / App Runner
1. Use `Dockerfile` for containerization
2. Set environment variables in task definition
3. Build and push Docker image
4. Deploy container

### Direct EC2
1. Install Python 3.11+
2. Install dependencies: `pip install -r requirements.txt`
3. Run with Gunicorn: `gunicorn wsgi:application`
4. Use systemd or PM2 for process management

## ✅ Verification Steps

After deployment:
1. ✅ Check health endpoint: `https://your-domain/api/health`
2. ✅ Test Google Sheets connection: `https://your-domain/api/sheets/diagnose`
3. ✅ Test form submission: `https://your-domain/api/form-submit`
4. ✅ Verify data appears in Google Sheet

## 🔒 Security Notes

- ✅ Never commit `.env` files
- ✅ Never commit service account JSON files
- ✅ Use AWS Secrets Manager or Parameter Store for sensitive data
- ✅ Enable HTTPS in production
- ✅ Set `ALLOWED_ORIGINS` to your frontend domain
- ✅ Set `FLASK_ENV=production`

## 📝 Next Steps

1. Review and set all required environment variables in AWS
2. Test deployment in staging environment first
3. Verify Google Sheets integration works
4. Monitor logs for any errors
5. Set up monitoring and alerts

