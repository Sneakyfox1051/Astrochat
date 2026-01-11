# Google Sheets Upload Debugging Guide

If data is not being uploaded to Google Sheets, follow these steps to diagnose and fix the issue.

## Step 1: Check if Google Sheets Integration is Enabled

Test the connection using the diagnose endpoint:

```bash
curl https://your-aws-backend-url/api/sheets/diagnose
```

**Expected Response (Success):**
```json
{
  "ok": true,
  "spreadsheet_id": "your_spreadsheet_id",
  "title": "Your Sheet Name",
  "sheets": ["Sheet1"],
  "presence": {
    "SERVICE_ACCOUNT_JSON": true,
    "GOOGLE_SHEETS_SPREADSHEET_ID": true
  },
  "env": {
    "GOOGLE_SERVICE_ACCOUNT_JSON": true,
    "GOOGLE_SHEETS_SPREADSHEET_ID": true,
    "append_form_submission_available": true
  }
}
```

**If you see `"ok": false`, check:**
- `GOOGLE_SERVICE_ACCOUNT_JSON` is set in AWS environment variables
- `GOOGLE_SHEETS_SPREADSHEET_ID` is set in AWS environment variables
- The service account email has access to the spreadsheet

## Step 2: Test Writing to Google Sheets

Test if you can write data:

```bash
curl -X POST https://your-aws-backend-url/api/sheets/test-write
```

**Expected Response (Success):**
```json
{
  "ok": true,
  "message": "Test data successfully written to Google Sheets",
  "data": [...]
}
```

**If this fails, check the error message:**
- Authentication errors: Service account JSON is invalid
- Permission errors: Spreadsheet not shared with service account
- API errors: Google Sheets API not enabled

## Step 3: Check AWS Environment Variables

In AWS Elastic Beanstalk Console:
1. Go to **Configuration** → **Software** → **Environment properties**
2. Verify these variables are set:
   - `GOOGLE_SERVICE_ACCOUNT_JSON` - Should contain the full JSON (single line)
   - `GOOGLE_SHEETS_SPREADSHEET_ID` - Your spreadsheet ID
   - `GOOGLE_SHEETS_WORKSHEET_NAME` - Usually "Sheet1"

## Step 4: Verify Google Cloud Setup

1. **Service Account Created:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Navigate to **IAM & Admin** → **Service Accounts**
   - Verify your service account exists

2. **Google Sheets API Enabled:**
   - Go to **APIs & Services** → **Library**
   - Search for "Google Sheets API"
   - Ensure it's **Enabled**

3. **Spreadsheet Shared:**
   - Open your Google Sheet
   - Click **Share** button
   - Add the service account email (ends with `@project.iam.gserviceaccount.com`)
   - Give it **Editor** permissions
   - Click **Send**

## Step 5: Check Application Logs

View AWS CloudWatch logs to see detailed error messages:

1. Go to **AWS Console** → **Elastic Beanstalk** → Your Environment
2. Click **Logs** → **Request Logs** → **Last 100 Lines**
3. Look for errors containing:
   - "Google Sheets integration failed"
   - "Google Sheets API error"
   - "Missing spreadsheet id or service account configuration"

## Step 6: Common Issues and Solutions

### Issue 1: "Google Sheets integration not configured"
**Solution:** Set `GOOGLE_SERVICE_ACCOUNT_JSON` or `GOOGLE_SERVICE_ACCOUNT_FILE` in AWS environment variables

### Issue 2: "Missing spreadsheet id"
**Solution:** Set `GOOGLE_SHEETS_SPREADSHEET_ID` in AWS environment variables

### Issue 3: "Permission denied" or "403 Forbidden"
**Solution:** Share the Google Sheet with the service account email (Editor permissions)

### Issue 4: "Invalid credentials"
**Solution:** 
- Verify the JSON is valid (no line breaks, proper escaping)
- Re-download the service account JSON from Google Cloud Console
- Update the `GOOGLE_SERVICE_ACCOUNT_JSON` environment variable

### Issue 5: Data appears but in wrong columns
**Solution:** Ensure your Google Sheet has these column headers in Row 1:
- Column A: Timestamp
- Column B: Name
- Column C: Phone Number
- Column D: Date of Birth
- Column E: Time of Birth
- Column F: Place
- Column G: Timezone
- Column H: Mode
- Column I: Rating
- Column J: Feedback Text

## Step 7: Verify Form Submission

When a user submits the form, check:
1. Browser console for errors (F12 → Console)
2. Network tab to see if `/api/form-submit` is called
3. Response from the API (should be 200 OK)

## Step 8: Manual Test

Test the form submission endpoint directly:

```bash
curl -X POST https://your-aws-backend-url/api/form-submit \
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

Then check your Google Sheet - a new row should appear.

## Still Not Working?

1. Check CloudWatch logs for detailed error messages
2. Verify all environment variables are set correctly
3. Test the `/api/sheets/diagnose` endpoint
4. Test the `/api/sheets/test-write` endpoint
5. Ensure the spreadsheet is shared with the service account
6. Verify Google Sheets API is enabled in Google Cloud Console

## Column Structure Reference

The code writes data in this order:
- **Column A:** Timestamp (ISO format)
- **Column B:** Name
- **Column C:** Phone Number
- **Column D:** Date of Birth
- **Column E:** Time of Birth
- **Column F:** Place
- **Column G:** Timezone
- **Column H:** Mode (kundli/horary)
- **Column I:** Rating (empty for form submissions)
- **Column J:** Feedback Text (empty for form submissions)




