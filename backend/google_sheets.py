"""
Google Sheets Integration Module for AstroRemedis Backend

This module handles all Google Sheets operations including:
- Service Account authentication
- Form data submission to Google Sheets
- Connection diagnostics and validation

Author: AstroRemedis Development Team
Version: 2.0.0
Last Updated: 2024
"""

import os
import json
import logging
from typing import List
from datetime import datetime
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Set up logger
logger = logging.getLogger(__name__)

# Google Sheets API scopes - allows read/write access to spreadsheets
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _get_env_trimmed(name: str) -> str | None:
    """
    Get environment variable with whitespace trimming.
    
    Args:
        name (str): Environment variable name
        
    Returns:
        str | None: Trimmed value or None if empty/missing
    """
    value = os.getenv(name)
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None


def _build_service_account_credentials_from_env() -> ServiceAccountCredentials:
    """
    Construct Google Service Account Credentials from environment variables.
    
    Supports three methods (in order of priority):
    1. GOOGLE_SERVICE_ACCOUNT_JSON: Raw JSON string containing service account key
    2. GOOGLE_SERVICE_ACCOUNT_FILE: Path to JSON key file
    3. Default: Looks for astroremedis-*.json files in backend directory
    
    Returns:
        ServiceAccountCredentials: Authenticated credentials object
        
    Raises:
        RuntimeError: If no valid service account configuration is found
    """
    import os
    import glob
    
    raw_json = _get_env_trimmed("GOOGLE_SERVICE_ACCOUNT_JSON")
    file_path = _get_env_trimmed("GOOGLE_SERVICE_ACCOUNT_FILE")

    # Method 1: Use JSON string from environment variable
    if raw_json:
        # Parse JSON string and create credentials
        info = json.loads(raw_json)
        return ServiceAccountCredentials.from_service_account_info(
            info,
            scopes=SCOPES,
        )
    
    # Method 2: Use file path from environment variable
    if file_path:
        # Handle both absolute and relative paths
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        if not os.path.isabs(file_path):
            # If relative path, make it relative to backend directory
            file_path = os.path.join(backend_dir, file_path)
        
        # Verify file exists
        if os.path.exists(file_path):
            # File exists, use it
            try:
                # Verify it's valid JSON
                with open(file_path, 'r') as f:
                    json.load(f)  # Validate JSON structure
                return ServiceAccountCredentials.from_service_account_file(file_path, scopes=SCOPES)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Service account file is not valid JSON: {e}")
            except Exception as e:
                raise RuntimeError(f"Error reading service account file: {e}")
        else:
            # File specified in env var doesn't exist, try auto-detection as fallback
            pattern = os.path.join(backend_dir, "astroremedis-*.json")
            matching_files = glob.glob(pattern)
            if matching_files:
                # Use the first matching file found
                file_path = matching_files[0]
                try:
                    with open(file_path, 'r') as f:
                        json.load(f)  # Validate JSON structure
                    return ServiceAccountCredentials.from_service_account_file(file_path, scopes=SCOPES)
                except json.JSONDecodeError as e:
                    raise RuntimeError(f"Service account file is not valid JSON: {e}")
                except Exception as e:
                    raise RuntimeError(f"Error reading service account file: {e}")
            else:
                raise RuntimeError(
                    f"Service account file not found: {file_path}. "
                    f"Also tried auto-detecting astroremedis-*.json files in {backend_dir} but none found."
                )
    
    # Method 3: Auto-detect astroremedis-*.json file in backend directory
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    pattern = os.path.join(backend_dir, "astroremedis-*.json")
    matching_files = glob.glob(pattern)
    
    if matching_files:
        # Use the first matching file
        file_path = matching_files[0]
        try:
            # Verify it's valid JSON
            with open(file_path, 'r') as f:
                json.load(f)  # Validate JSON structure
            return ServiceAccountCredentials.from_service_account_file(file_path, scopes=SCOPES)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Service account file is not valid JSON: {e}")
        except Exception as e:
            raise RuntimeError(f"Error reading service account file: {e}")

    raise RuntimeError(
        "Missing service account configuration. "
        "Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE, "
        "or place an astroremedis-*.json file in the backend directory."
    )


def _build_credentials_from_env() -> ServiceAccountCredentials:
    """
    Return Google API credentials using Service Account authentication.
    
    This function uses ONLY service account authentication (no OAuth refresh tokens).
    This approach is more secure and doesn't require user consent.
    
    Returns:
        ServiceAccountCredentials: Authenticated credentials for Google Sheets API
    """
    return _build_service_account_credentials_from_env()


def _get_spreadsheet_id() -> str:
    """
    Get the target Google Spreadsheet ID from environment variables.
    
    Returns:
        str: The spreadsheet ID
        
    Raises:
        RuntimeError: If GOOGLE_SHEETS_SPREADSHEET_ID is not set
    """
    spreadsheet_id = _get_env_trimmed("GOOGLE_SHEETS_SPREADSHEET_ID")
    if not spreadsheet_id:
        raise RuntimeError("Missing GOOGLE_SHEETS_SPREADSHEET_ID in environment.")
    return spreadsheet_id


def append_form_submission(spreadsheet_name: str, worksheet_name: str, row_data: List[str]) -> None:
    """
    Append form submission data to Google Sheets.
    
    This function takes user form data and appends it as a new row to the specified
    Google Sheet. It's used to store user birth details and form submissions.
    
    Column structure:
    - Column A: Timestamp
    - Column B: Name
    - Column C: Phone Number
    - Column D: Date of Birth
    - Column E: Time of Birth
    - Column F: Place
    - Column G: Timezone
    - Column H: Mode (kundli/horary)
    - Column I: Rating (empty for form-only rows)
    - Column J: Feedback Text (empty for form-only rows)
    
    Args:
        spreadsheet_name (str): Name of the spreadsheet (for logging)
        worksheet_name (str): Name of the worksheet/tab (defaults to 'Sheet1')
        row_data (List[str]): List of data to append [timestamp, name, phone, dob, tob, place, timezone, mode, rating, feedback]
        
    Raises:
        RuntimeError: If Google Sheets API error occurs or authentication fails
    """
    # Get authenticated credentials
    creds = _build_credentials_from_env()
    
    try:
        # Build Google Sheets API service
        service = build("sheets", "v4", credentials=creds)
        spreadsheet_id = _get_spreadsheet_id()
        
        # Determine target worksheet (default to 'Sheet1' if not specified)
        sheet_tab = worksheet_name or 'Sheet1'
        range_name = f"{sheet_tab}!A1"  # Append to first available row in column A

        # Prepare data for insertion
        body = {
            "values": [row_data]
        }

        # Execute the append operation
        # Use RAW to prevent Google Sheets from auto-converting dates/times to serial numbers
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="RAW",  # RAW preserves exact text format (prevents date/time auto-conversion)
            insertDataOption="INSERT_ROWS",   # Always insert new rows
            body=body
        ).execute()
        
    except HttpError as he:
        # Re-raise Google Sheets API errors with context
        raise RuntimeError(f"Google Sheets API error: {he}")
    except Exception as e:
        # Catch any other errors (network, auth, etc.)
        raise RuntimeError(f"Failed to append to Google Sheet: {e}")


def update_row_with_feedback(spreadsheet_name: str, worksheet_name: str, user_name: str, rating: str, feedback_text: str) -> None:
    """
    Update the most recent form submission row with feedback data.
    
    Finds the most recent row for the given user name that has empty rating/feedback,
    and updates columns I (Rating) and J (Feedback Text) with the feedback data.
    
    Column structure:
    - Column A: Timestamp
    - Column B: Name
    - Column C: Phone Number
    - Column D: Date of Birth
    - Column E: Time of Birth
    - Column F: Place
    - Column G: Timezone
    - Column H: Mode (kundli/horary)
    - Column I: Rating
    - Column J: Feedback Text
    
    Args:
        spreadsheet_name (str): Name of the spreadsheet (for logging)
        worksheet_name (str): Name of the worksheet/tab
        user_name (str): User's name to match
        rating (str): Rating value (1-5)
        feedback_text (str): Feedback text
        
    Raises:
        RuntimeError: If Google Sheets API error occurs or authentication fails
    """
    # Get authenticated credentials
    creds = _build_credentials_from_env()
    
    try:
        # Build Google Sheets API service
        service = build("sheets", "v4", credentials=creds)
        spreadsheet_id = _get_spreadsheet_id()
        
        # Determine target worksheet
        sheet_tab = worksheet_name or 'Sheet1'
        
        # Get all data from the sheet
        range_name = f"{sheet_tab}!A2:J"  # Start from row 2 (skip header), include all columns up to J (Feedback)
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        
        if not values:
            # No data found, append as new row
            logger.warning(f"No form data found for user {user_name}, appending feedback as new row")
            # Use the same append function but with feedback data
            creds = _build_credentials_from_env()
            service = build("sheets", "v4", credentials=creds)
            spreadsheet_id = _get_spreadsheet_id()
            sheet_tab = worksheet_name or 'Sheet1'
            range_name = f"{sheet_tab}!A1"
            body = {
                "values": [[
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Column A: Timestamp
                    user_name,  # Column B: Name
                    '',  # Column C: Phone Number (empty)
                    '',  # Column D: Date of Birth (empty)
                    '',  # Column E: Time of Birth (empty)
                    '',  # Column F: Place (empty)
                    '',  # Column G: Timezone (empty)
                    '',  # Column H: Mode (empty)
                    str(rating),  # Column I: Rating
                    feedback_text or 'N/A'  # Column J: Feedback Text
                ]]
            }
            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="RAW",  # RAW preserves exact text format
                insertDataOption="INSERT_ROWS",
                body=body
            ).execute()
            return
        
        # Find the most recent row with matching name and empty rating/feedback
        # Search from bottom to top (most recent first)
        row_index = None
        for i in range(len(values) - 1, -1, -1):
            row = values[i]
            # Check if row has enough columns and matches the name
            if len(row) > 1 and row[1] == user_name:  # Column B is index 1 (Name)
                # Check if rating is empty (column I is index 8)
                if len(row) <= 9 or not row[8] or row[8].strip() == '':
                    row_index = i + 2  # +2 because we started from row 2 (1-indexed + header)
                    break
        
        if row_index:
            # Update the existing row (columns I and J for Rating and Feedback)
            update_range = f"{sheet_tab}!I{row_index}:J{row_index}"
            body = {
                "values": [[str(rating), feedback_text or 'N/A']]
            }
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=update_range,
                valueInputOption="RAW",  # Use RAW to preserve exact text format
                body=body
            ).execute()
            logger.info(f"Updated row {row_index} with feedback for user {user_name}")
        else:
            # No matching row found, append as new row
            logger.warning(f"No matching form submission found for user {user_name}, appending feedback as new row")
            # Use the same append logic but with feedback data
            creds = _build_credentials_from_env()
            service = build("sheets", "v4", credentials=creds)
            spreadsheet_id = _get_spreadsheet_id()
            sheet_tab = worksheet_name or 'Sheet1'
            range_name = f"{sheet_tab}!A1"
            body = {
                "values": [[
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Column A: Timestamp
                    user_name,  # Column B: Name
                    '',  # Column C: Phone Number (empty)
                    '',  # Column D: Date of Birth (empty)
                    '',  # Column E: Time of Birth (empty)
                    '',  # Column F: Place (empty)
                    '',  # Column G: Timezone (empty)
                    '',  # Column H: Mode (empty)
                    str(rating),  # Column I: Rating
                    feedback_text or 'N/A'  # Column J: Feedback Text
                ]]
            }
            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="RAW",  # RAW preserves exact text format
                insertDataOption="INSERT_ROWS",
                body=body
            ).execute()
        
    except HttpError as he:
        raise RuntimeError(f"Google Sheets API error: {he}")
    except Exception as e:
        raise RuntimeError(f"Failed to update row with feedback: {e}")


def append_feedback_submission(spreadsheet_name: str, worksheet_name: str, row_data: List[str]) -> None:
    """
    Append feedback submission data to Google Sheets.
    
    This function takes user feedback data (rating and comments) and appends it as a new row
    to the specified Google Sheet. It's used to store user feedback after chat sessions.
    
    Args:
        spreadsheet_name (str): Name of the spreadsheet (for logging)
        worksheet_name (str): Name of the worksheet/tab (defaults to 'Feedback')
        row_data (List[str]): List of data to append [timestamp, rating, feedback_text]
        
    Raises:
        RuntimeError: If Google Sheets API error occurs or authentication fails
    """
    # Get authenticated credentials
    creds = _build_credentials_from_env()
    
    try:
        # Build Google Sheets API service
        service = build("sheets", "v4", credentials=creds)
        spreadsheet_id = _get_spreadsheet_id()
        
        # Determine target worksheet (default to 'Feedback' if not specified)
        sheet_tab = worksheet_name or 'Feedback'
        range_name = f"{sheet_tab}!A1"  # Append to first available row in column A

        # Prepare data for insertion
        body = {
            "values": [row_data]
        }

        # Execute the append operation
        # Use RAW to prevent Google Sheets from auto-converting dates/times to serial numbers
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="RAW",  # RAW preserves exact text format (prevents date/time auto-conversion)
            insertDataOption="INSERT_ROWS",   # Always insert new rows
            body=body
        ).execute()
        
    except HttpError as he:
        # Re-raise Google Sheets API errors with context
        raise RuntimeError(f"Google Sheets API error: {he}")
    except Exception as e:
        # Catch any other errors (network, auth, etc.)
        raise RuntimeError(f"Failed to append feedback to Google Sheet: {e}")


def diagnose_connection() -> dict:
    """
    Diagnose Google Sheets connection and configuration.
    
    This function checks:
    1. Environment variable presence
    2. Service account configuration
    3. Spreadsheet access permissions
    4. Returns spreadsheet metadata if successful
    
    Returns:
        dict: Diagnostic information including:
            - ok (bool): Whether connection is successful
            - presence (dict): Which environment variables are set
            - spreadsheet_id (str): Target spreadsheet ID
            - title (str): Spreadsheet title
            - sheets (list): Available worksheet names
            - error (str): Error message if connection failed
    """
    # Check environment variable presence first
    presence = {
        "SERVICE_ACCOUNT_JSON": bool(_get_env_trimmed("GOOGLE_SERVICE_ACCOUNT_JSON")),
        "SERVICE_ACCOUNT_FILE": bool(_get_env_trimmed("GOOGLE_SERVICE_ACCOUNT_FILE")),
        "GOOGLE_SHEETS_SPREADSHEET_ID": bool(_get_env_trimmed("GOOGLE_SHEETS_SPREADSHEET_ID")),
    }
    
    # Check if we have required configuration
    have_service_account = presence["SERVICE_ACCOUNT_JSON"] or presence["SERVICE_ACCOUNT_FILE"]
    if not presence["GOOGLE_SHEETS_SPREADSHEET_ID"] or not have_service_account:
        return {
            "ok": False, 
            "presence": presence, 
            "error": "Missing spreadsheet id or service account configuration."
        }

    # Attempt to connect and fetch spreadsheet metadata
    try:
        # Build authenticated service
        creds = _build_credentials_from_env()
        service = build("sheets", "v4", credentials=creds)
        spreadsheet_id = _get_spreadsheet_id()
        
        # Fetch spreadsheet metadata
        meta = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id, 
            includeGridData=False  # We only need metadata, not cell data
        ).execute()
        
        # Extract useful information
        title = meta.get('properties', {}).get('title')
        sheets = [s.get('properties', {}).get('title') for s in meta.get('sheets', [])]
        
        return {
            "ok": True,
            "spreadsheet_id": spreadsheet_id,
            "title": title,
            "sheets": sheets,
            "presence": presence,
        }
        
    except HttpError as he:
        # Google Sheets API specific error
        return {
            "ok": False, 
            "presence": presence, 
            "error": f"Google Sheets API error: {he}"
        }
    except Exception as e:
        # General error (network, auth, etc.)
        return {
            "ok": False, 
            "presence": presence, 
            "error": str(e)
        }


