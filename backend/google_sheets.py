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
from typing import List
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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
    
    Supports two methods:
    1. GOOGLE_SERVICE_ACCOUNT_JSON: Raw JSON string containing service account key
    2. GOOGLE_SERVICE_ACCOUNT_FILE: Path to JSON key file
    
    Returns:
        ServiceAccountCredentials: Authenticated credentials object
        
    Raises:
        RuntimeError: If neither JSON nor file path is configured
    """
    raw_json = _get_env_trimmed("GOOGLE_SERVICE_ACCOUNT_JSON")
    file_path = _get_env_trimmed("GOOGLE_SERVICE_ACCOUNT_FILE")

    if raw_json:
        # Parse JSON string and create credentials
        info = json.loads(raw_json)
        return ServiceAccountCredentials.from_service_account_info(
            info,
            scopes=SCOPES,
        )
    if file_path:
        # Load credentials from file path
        return ServiceAccountCredentials.from_service_account_file(file_path, scopes=SCOPES)

    raise RuntimeError("Missing service account configuration. Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE.")


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
    
    Args:
        spreadsheet_name (str): Name of the spreadsheet (for logging)
        worksheet_name (str): Name of the worksheet/tab (defaults to 'Sheet1')
        row_data (List[str]): List of data to append [timestamp, name, dob, tob, place, timezone]
        
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
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",  # Allows formulas and formatting
            insertDataOption="INSERT_ROWS",   # Always insert new rows
            body=body
        ).execute()
        
    except HttpError as he:
        # Re-raise Google Sheets API errors with context
        raise RuntimeError(f"Google Sheets API error: {he}")
    except Exception as e:
        # Catch any other errors (network, auth, etc.)
        raise RuntimeError(f"Failed to append to Google Sheet: {e}")


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


