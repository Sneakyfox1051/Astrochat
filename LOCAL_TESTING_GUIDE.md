# Local Testing Guide for Google Sheets Integration

Follow these steps to test Google Sheets integration on your local system before deploying to AWS.

## Step 1: Set Up Your .env File

Create or edit `backend/.env` file with the following variables:

```env
# ProKerala API (Required for Kundli)
PROKERALA_CLIENT_ID=your_prokerala_client_id
PROKERALA_CLIENT_SECRET=your_prokerala_client_secret

# OpenAI API (Required for AI)
OPENAI_API_KEY=your_openai_api_key

# Google Sheets Service Account (Choose ONE method)
# Method 1: JSON file path (recommended for local)
GOOGLE_SERVICE_ACCOUNT_FILE=path/to/your-service-account.json

# Method 2: JSON as string (alternative)
# GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"..."}

# Google Sheets Configuration
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id_here
GOOGLE_SHEETS_WORKSHEET_NAME=Sheet1
GOOGLE_SHEETS_SPREADSHEET_NAME=AstroRemedis Data

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True
PORT=5000
```

## Step 2: Get Google Service Account Credentials

1. **Go to Google Cloud Console:**
   - Visit https://console.cloud.google.com/
   - Create a new project or select existing one

2. **Enable Google Sheets API:**
   - Go to **APIs & Services** → **Library**
   - Search for "Google Sheets API"
   - Click **Enable**

3. **Create Service Account:**
   - Go to **IAM & Admin** → **Service Accounts**
   - Click **Create Service Account**
   - Name it (e.g., "astroremedis-local")
   - Click **Create and Continue**
   - Skip role assignment (click **Continue**)
   - Click **Done**

4. **Create and Download Key:**
   - Click on the service account you just created
   - Go to **Keys** tab
   - Click **Add Key** → **Create new key**
   - Choose **JSON** format
   - Download the JSON file
   - Save it in your project (e.g., `backend/service-account.json`)

5. **Share Your Google Sheet:**
   - Open your Google Sheet
   - Click **Share** button
   - Add the service account email (from the JSON file, field `client_email`)
   - Give it **Editor** permissions
   - Click **Send**

## Step 3: Update Your .env File

Add the path to your service account JSON file:

```env
GOOGLE_SERVICE_ACCOUNT_FILE=service-account.json
```

Or if you want to use the JSON string method, copy the entire JSON content and paste it (as a single line):

```env
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"...","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"...@project.iam.gserviceaccount.com","client_id":"...","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"..."}
```

**Get Your Spreadsheet ID:**
- Open your Google Sheet
- Look at the URL: `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_HERE/edit`
- Copy the `SPREADSHEET_ID_HERE` part
- Add it to `.env`: `GOOGLE_SHEETS_SPREADSHEET_ID=SPREADSHEET_ID_HERE`

## Step 4: Start the Backend Server

```bash
# Navigate to backend directory
cd backend

# Install dependencies (if not already done)
pip install -r ../requirements.txt

# Start the server
python app.py
```

The server should start on `http://localhost:5000`

## Step 5: Test the Connection

### Test 1: Diagnose Connection

Open in browser or use curl:
```bash
curl http://localhost:5000/api/sheets/diagnose
```

**Expected Response (Success):**
```json
{
  "ok": true,
  "spreadsheet_id": "your_spreadsheet_id",
  "title": "Your Sheet Name",
  "sheets": ["Sheet1"],
  "presence": {
    "SERVICE_ACCOUNT_JSON": false,
    "SERVICE_ACCOUNT_FILE": true,
    "GOOGLE_SHEETS_SPREADSHEET_ID": true
  },
  "env": {
    "GOOGLE_SERVICE_ACCOUNT_JSON": false,
    "GOOGLE_SERVICE_ACCOUNT_FILE": true,
    "GOOGLE_SHEETS_SPREADSHEET_ID": true,
    "append_form_submission_available": true
  }
}
```

**If you see `"ok": false`:**
- Check that `GOOGLE_SERVICE_ACCOUNT_FILE` path is correct
- Verify the JSON file exists and is valid
- Check that `GOOGLE_SHEETS_SPREADSHEET_ID` is set

### Test 2: Test Writing Data

```bash
curl -X POST http://localhost:5000/api/sheets/test-write
```

**Expected Response (Success):**
```json
{
  "ok": true,
  "message": "Test data successfully written to Google Sheets",
  "data": [...]
}
```

**Check your Google Sheet** - you should see a new row with test data!

### Test 3: Test Form Submission

```bash
curl -X POST http://localhost:5000/api/form-submit \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "phone": "1234567890",
    "dob": "1990-01-01",
    "tob": "12:00:00",
    "place": "Delhi",
    "timezone": "Asia/Kolkata",
    "mode": "kundli"
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Form submitted successfully"
}
```

**Check your Google Sheet** - you should see a new row with the form data!

## Step 6: Test from Frontend

1. **Start the frontend:**
   ```bash
   cd frontend
   npm start
   ```

2. **Open the app:**
   - Go to `http://localhost:3000`
   - Fill out the form
   - Submit it

3. **Check Google Sheet:**
   - Open your Google Sheet
   - Verify the data appears in the correct columns

## Troubleshooting Local Issues

### Issue 1: "Google Sheets integration not configured"
**Solution:**
- Check that `GOOGLE_SERVICE_ACCOUNT_FILE` or `GOOGLE_SERVICE_ACCOUNT_JSON` is in `.env`
- Verify the file path is correct (relative to `backend/` directory)
- Check that the JSON file is valid

### Issue 2: "Missing spreadsheet id"
**Solution:**
- Add `GOOGLE_SHEETS_SPREADSHEET_ID` to your `.env` file
- Verify the spreadsheet ID is correct (from the Google Sheet URL)

### Issue 3: "Permission denied" or "403 Forbidden"
**Solution:**
- Share the Google Sheet with the service account email
- Give it **Editor** permissions
- The service account email is in the JSON file (`client_email` field)

### Issue 4: "File not found"
**Solution:**
- If using `GOOGLE_SERVICE_ACCOUNT_FILE`, make sure the path is relative to `backend/` directory
- Or use absolute path: `GOOGLE_SERVICE_ACCOUNT_FILE=/full/path/to/service-account.json`

### Issue 5: Data not appearing in Google Sheet
**Check:**
1. Server logs for errors
2. That the spreadsheet is shared with service account
3. That the worksheet name matches (default is "Sheet1")
4. Column headers are in Row 1 (the code appends to Row 2+)

## Column Structure

Make sure your Google Sheet has these column headers in **Row 1**:
- **Column A:** Timestamp
- **Column B:** Name
- **Column C:** Phone Number
- **Column D:** Date of Birth
- **Column E:** Time of Birth
- **Column F:** Place
- **Column G:** Timezone
- **Column H:** Mode
- **Column I:** Rating
- **Column J:** Feedback Text

## Next Steps

Once local testing works:
1. Copy the same environment variables to AWS Elastic Beanstalk
2. Use `GOOGLE_SERVICE_ACCOUNT_JSON` (as string) in AWS instead of file path
3. Deploy and test on AWS

## Quick Test Script

Save this as `test_sheets.py` in the project root:

```python
import requests
import json

BASE_URL = "http://localhost:5000"

# Test 1: Diagnose
print("Testing connection...")
response = requests.get(f"{BASE_URL}/api/sheets/diagnose")
print(f"Diagnose: {response.status_code}")
print(json.dumps(response.json(), indent=2))

# Test 2: Test Write
print("\nTesting write...")
response = requests.post(f"{BASE_URL}/api/sheets/test-write")
print(f"Test Write: {response.status_code}")
print(json.dumps(response.json(), indent=2))

# Test 3: Form Submit
print("\nTesting form submit...")
response = requests.post(
    f"{BASE_URL}/api/form-submit",
    json={
        "name": "Test User",
        "phone": "1234567890",
        "dob": "1990-01-01",
        "tob": "12:00:00",
        "place": "Delhi",
        "timezone": "Asia/Kolkata",
        "mode": "kundli"
    }
)
print(f"Form Submit: {response.status_code}")
print(json.dumps(response.json(), indent=2))
```

Run it:
```bash
pip install requests
python test_sheets.py
```




