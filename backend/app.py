"""
AstroRemedis Backend API - Enhanced Astrology Chatbot

This is the main backend server for AstroRemedis, providing:
- AI-powered astrology consultations using OpenAI Assistant API
- Kundli chart generation via ProKerala API (6 endpoints)
- Real-time chat with spiritual Pandit Ji persona
- Google Sheets integration for data storage (optional)

Key Features:
- OpenAI Assistant API integration (replaces RAG pipeline)
  - Default Assistant for normal Kundli flow
  - Horary Assistant for KP Horary analysis (1-249 number method)
- ProKerala API integration:
  - /v2/astrology/planet-position - Planetary positions
  - /v2/astrology/kundli/advanced - Advanced Kundli data
  - /v2/astrology/bhava-position - House positions
  - /v2/astrology/mangal-dosha - Mangal Dosha analysis
  - /v2/astrology/auspicious-yoga - Auspicious Yoga
  - /v2/astrology/sade-sati - Sade Sati analysis
  - /v2/astrology/chart - Visual SVG chart
  - /v2/astrology/kaal-sarp-dosha - Kaal Sarp Dosha analysis
  - /v2/astrology/upagraha-position - Upagraha positions
  - /v2/astrology/yoga - General Yoga analysis
  - /v2/astrology/dasha-periods - Dasha periods
  - /v2/astrology/planet-relationship - Planet relationships
  - /v2/astrology/divisional-planet-position - Divisional planet positions
  - /v2/astrology/chandrashtama-periods - Chandrashtama periods
- HTTP connection pooling for faster API calls
- Geocoding cache for repeated place lookups
- Age-based prediction logic for realistic responses
- Remedy recommendations (free and paid)

Architecture:
- All predictions are handled by OpenAI Assistants (no local generation)
- Assistant selection based on form/flow type (normal vs horary)
- Chart data is compacted before sending to Assistant API to avoid token limits

Author: AstroRemedis Development Team
Version: 2.1.0
Last Updated: 2024
"""

import os
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import threading
# Suppress ChromaDB telemetry warnings (for any transitive dependencies)
os.environ['CHROMA_TELEMETRY'] = 'false'
# Suppress ONNX Runtime GPU warnings (for any transitive dependencies)
warnings.filterwarnings('ignore', category=UserWarning, module='onnxruntime')

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import logging
import pytz
import openai
from dotenv import load_dotenv
from googleapiclient.errors import HttpError

# Configure logging early (needed for early warnings)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import config module - handle both local and deployment scenarios
import sys

# Ensure backend directory is in Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

try:
    from config import FOLLOW_UP_QUESTIONS, QUESTION_INTROS, RESPONSE_STYLE_MAP
except ImportError as e:
    # If import still fails, log the error and use defaults
    logger.error(f"Failed to import config module: {e}")
    logger.error(f"Python path: {sys.path}")
    logger.error(f"Backend directory: {backend_dir}")
    if os.path.exists(backend_dir):
        try:
            logger.error(f"Files in backend directory: {os.listdir(backend_dir)}")
        except Exception as list_err:
            logger.error(f"Could not list directory: {list_err}")
    else:
        logger.error("Backend directory not found")
    # Use empty defaults to prevent complete failure
    FOLLOW_UP_QUESTIONS = {}
    QUESTION_INTROS = []
    RESPONSE_STYLE_MAP = {}

# RAG functionality removed; Assistant API is used exclusively

# Custom embeddings and vector store removed

# Environment Configuration
# Load environment variables from backend/.env file
ENV_PATH = os.path.join(os.path.dirname(__file__), '.env')
# Force override to ensure backend/.env values are used even if shell has different vars
ENV_LOADED = load_dotenv(ENV_PATH, override=True)

app = Flask(__name__)
# ============================================================================
# CORS Configuration
# ============================================================================
# Enable CORS for frontend communication
# In production, restrict to specific domains via ALLOWED_ORIGINS env var
# Default: '*' (allows all origins) - CHANGE THIS IN PRODUCTION!
# Production: Set ALLOWED_ORIGINS to your Netlify frontend URL
# Example: ALLOWED_ORIGINS=https://astroremedis.netlify.app
allowed_origins = os.getenv('ALLOWED_ORIGINS', '*')
if allowed_origins != '*':
    # Parse comma-separated origins (supports multiple domains)
    allowed_origins = [origin.strip() for origin in allowed_origins.split(',')]
    logger.info(f"CORS configured for origins: {allowed_origins}")
else:
    logger.warning("CORS is set to allow all origins (*). This should be restricted in production!")

CORS(app, resources={
    r"/api/*": {
        "origins": allowed_origins,
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

# Add security headers to all responses
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    # Only add HSTS in production with HTTPS
    if os.getenv('FLASK_ENV') == 'production' and request.is_secure:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# API Configuration
# ProKerala API credentials for Kundli chart generation
PROKERALA_CLIENT_ID = os.getenv('PROKERALA_CLIENT_ID')
PROKERALA_CLIENT_SECRET = os.getenv('PROKERALA_CLIENT_SECRET')

# OpenAI API key for AI-powered astrology consultations
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
# OpenAI Assistant ID for Assistant API (replaces RAG pipeline)
OPENAI_ASSISTANT_ID = os.getenv('OPENAI_ASSISTANT_ID', 'asst_drztay8pmr9VrhWdM4r76tSM')

# Google Sheets configuration (using Service Account authentication)
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_TOKEN_URI = os.getenv('GOOGLE_TOKEN_URI', 'https://oauth2.googleapis.com/token')
GOOGLE_REFRESH_TOKEN = os.getenv('GOOGLE_REFRESH_TOKEN')
GOOGLE_SHEETS_SPREADSHEET_NAME = os.getenv('GOOGLE_SHEETS_SPREADSHEET_NAME', 'AstroRemedis Data')
GOOGLE_SHEETS_WORKSHEET_NAME = os.getenv('GOOGLE_SHEETS_WORKSHEET_NAME', 'Sheet1')

try:
    from google_sheets import append_form_submission, append_feedback_submission, diagnose_connection
    # Only enable if credentials are available
    if not os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON') and not os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE'):
        append_form_submission = None
        append_feedback_submission = None
        diagnose_connection = None
        logger.info("Google Sheets integration disabled - no credentials found")
except Exception as _e:
    append_form_submission = None
    append_feedback_submission = None
    diagnose_connection = None
    logger.warning(f"Google Sheets integration not available: {_e}")

# Default geographic constants for fallback when geocoding fails
DEFAULT_LAT, DEFAULT_LON = 19.0760, 72.8777  # Mumbai, India coordinates
DEFAULT_TZ = 'Asia/Kolkata'  # Indian Standard Time

# Set OpenAI API key
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# Remedies generator (Hinglish) - selects and formats remedies for common problem areas
def generate_remedies(user_query, chart_data, compact=False):
    """Select and format remedies using indirect Hinglish suggestions for free and paid items.
    If compact=True, return exactly one free and one paid item with a short CTA.
    """
    query_lower = (user_query or '').lower()
    problem_area = "8. Health, Energy aur Peace Remedies 8"  # Default to General

    if any(word in query_lower for word in ['job', 'business', 'career', 'naukri', 'rozi', 'work']):
        problem_area = "1. Career, Job aur Business ke liye Remedies 1"
    elif any(word in query_lower for word in ['partner', 'relationship', 'love', 'pyaar']):
        problem_area = "2. Love aur Relationship Remedies 2"
    elif any(word in query_lower for word in ['marriage', 'shadi', 'vivah', 'delays']):
        problem_area = "3. Marriage aur Compatibility Remedies 3"
    elif any(word in query_lower for word in ['child', 'santan', 'baby', 'bacche', 'family growth']):
        problem_area = "4. Santan Prapti aur Family Growth Remedies 4"
    elif any(word in query_lower for word in ['property', 'home', 'land', 'dispute']):
        problem_area = "5. Property, Home aur Land Stability Remedies 5"
    elif any(word in query_lower for word in ['court case', 'litigation', 'case']):
        problem_area = "6. Litigation aur Court Case Remedies 6"
    elif any(word in query_lower for word in ['money', 'finance', 'wealth', 'prosperity']):
        problem_area = "7. Finance, Money aur Prosperity Remedies 7"

    remedy_map = {
        "1. Career, Job aur Business ke liye Remedies 1": {
            "free": "Har subah, copper ke bartan se Surya Dev ko jal arpit karein (Surya Arghya). Isse aapka aatmavishwas aur netritva ki kshamta badhegi.",
            "buyable": [
                "Pyrite Bracelet: Aapke career aur dhan ki growth mein madad karta hai.",
                "Tiger Eye Bracelet: Aapko himmat aur focus deta hai.",
                "Small Kuber Yantra or Gomti Chakra: Apne desk par rakhein sampannta aur naye avsaron ke liye."
            ],
            "category_name": "Career aur Business"
        },
        "2. Love aur Relationship Remedies 2": {
            "free": "Shukrawar (Friday) ki shaam ko peepal ke ped ko doodh/jal arpit karein (peepal ke ped ko jal dene se rishte mazboot hote hain).",
            "buyable": [
                "Rose Quartz Bracelet: Pyaar aur achhe rishton ko aakarshit karta hai.",
                "Gauri Shankar Rudraksha: Jeevan saathi ke saath bandhan mazboot karta hai.",
                "Shukra Yantra: Ise ghar mein rakhne se partnership ki energy achhi rehti hai."
            ],
            "category_name": "Love aur Relationship"
        },
        "3. Marriage aur Compatibility Remedies 3": {
            "free": "Guruwar (Thursday) ka vrat rakhein ya gau mata ko hara chara khilayein (gair-khati ghass).",
            "buyable": [
                "Rose Quartz Bracelet: Shadi aur achhe rishton mein madad karta hai.",
                "Gauri Shankar Rudraksha: Vivah mein deri door karta hai aur dampatya sukh deta hai.",
                "Shukra Yantra: Prem aur sahayog badhane ke liye use karein."
            ],
            "category_name": "Marriage aur Compatibility"
        },
        "4. Santan Prapti aur Family Growth Remedies 4": {
            "free": "Bhagwan Krishna ki pooja karein aur Shukrawar ko unhe doodh ya makhan ka bhog lagayein.",
            "buyable": [
                "Putra Prapti Yantra (ya Haridra Ganesh Yantra): Santan sukh ke liye ashirwad deta hai.",
                "Moti (Pearl) Stone: Mann ki shanti aur matritva shakti ko badhata hai.",
                "Gauri Shankar Rudraksha: Parivar ki ekta aur unnati ke liye accha hai."
            ],
            "category_name": "Santan Prapti aur Family Growth"
        },
        "5. Property, Home aur Land Stability Remedies 5": {
            "free": "Har shaam ghar ke mukhya dwar (main entrance) par ek diya (deepak) jalayein.",
            "buyable": [
                "Turquoise Stone: Ghar ki suraksha aur sthirta ke liye.",
                "Vastu Yantra: Ghar ke North-East kone mein rakhein Vastu dosh dur karne ke liye.",
                "Red Jasper Bracelet: Zameen se jude vivaad aur sthirta ke liye."
            ],
            "category_name": "Property aur Home Stability"
        },
        "6. Litigation aur Court Case Remedies 6": {
            "free": "Mangalwar aur Shanivar ko Hanuman Chalisa ka path karein.",
            "buyable": [
                "Ganesha Yantra: Rukavatein (obstacles) hatane aur vivaad mein safalta ke liye.",
                "Tiger Eye Bracelet: Himmat aur focus deta hai court case ke dauran.",
                "Blue Sapphire (Neelam): Nyay aur jeet ke liye. (Astrologer ki salah zaroori hai pehenne se pehle)."
            ],
            "category_name": "Litigation aur Court Case"
        },
        "7. Finance, Money aur Prosperity Remedies 7": {
            "free": "Har roz, khaaskar Shukrawar ko, Kanakadhara Stotram ka path karein.",
            "buyable": [
                "Green Aventurine Bracelet: Dhan aur naye avsaron ko aakarshit karta hai (Stone of Opportunity).",
                "Shri Yantra: Cash box ya North-East kone mein rakhein dhan ki lagatar flow ke liye.",
                "Citrine Stone: Aamdani (abundance) badhane aur financial blockages hatane ke liye."
            ],
            "category_name": "Finance, Money aur Prosperity"
        },
        "8. Health, Energy aur Peace Remedies 8": {
            "free": "Har din Om Namah Shivaya mantra ka 108 baar jaap karein (apne saans par dhyaan dete hue).",
            "buyable": [
                "Amethyst Stone: Stress aur man ki shanti ke liye.",
                "Tulsi Mala: Swasthya (health), suraksha aur shuddhi (purification) ke liye pehnein.",
                "Health Yantra: Recovery aur urja ke liye apne bed ke paas rakhein."
            ],
            "category_name": "Health, Energy aur Peace"
        }
    }

    selected = remedy_map.get(problem_area, remedy_map["8. Health, Energy aur Peace Remedies 8"])
    activation_process = (
        "Apne item ko pehenne se pehle, usey Ganga Jal ya kachche doodh se saaf karein aur dhoop/chaandni mein energize karein. Is dauran 'Om Namah Shivaya' ka 11 baar jaap karein."
    )

    if compact:
        paid_one = selected['buyable'][0] if selected.get('buyable') else ''
        return (
            f"\n\nAdab ji, ghabrane ki koi baat nahi hai. Yadi aap chahte hain ki aapki problems thik ho ya kuch bhi use kar sakein, uske liye aap yeh upay kar sakte hain:\n\n"
            f"1. {selected['free']}\n"
            f"2. {paid_one} (AstroRemedis pe uplabdh hai)\n\n"
            f"Activation: {activation_process}"
        )
    else:
        response = (
            f"\n---\n\n"
            f"{selected['category_name']} ke liye upay:\n"
            f"- Free: {selected['free']}\n"
            f"- Paid options: \n  - " + "\n  - ".join(selected['buyable']) + "\n"
            f"- Activation: {activation_process}"
        )
        return response


def should_append_remedies(user_query: str) -> bool:
    """
    Determine if remedies should be appended to the response.
    
    Returns True only when the user expresses a problem/pain, not generic inquiries.
    This ensures remedies are not added for neutral questions like "career ke bare mein bataiye".
    
    Args:
        user_query (str): User's question/statement
    
    Returns:
        bool: True if remedies should be appended, False otherwise
    """
    if not user_query:
        return False
    q = user_query.lower()
    problem_markers = [
        'problem', 'issue', 'dikkat', 'pareshani', 'musibat', 'ruk', 'delay', 'deri',
        'nahi mil', 'nahi ho', 'stuck', 'loss', 'down', 'court', 'case', 'breakup',
        'health issue', 'bimari', 'paise ki dikkat', 'financial problem',
        'job nahi', 'promotion nahi', 'marriage delay', 'santan nahi',
        'tension', 'worried', 'concerned', 'anxiety', 'stress', 'chinta', 'fikar'
    ]
    return any(marker in q for marker in problem_markers)

class EnhancedAstroBotAPI:
    """
    Enhanced API class for AstroRemedis backend.
    
    Handles:
    - ProKerala API integration (token management, chart generation)
    - OpenAI Assistant API integration (predictions)
    - Geocoding with caching
    - HTTP connection pooling for performance
    """

    def _get_http(self) -> requests.Session:
        """
        Lazily initialize and return a shared HTTP session.
        
        Benefits:
        - Connection pooling (reuses TCP connections)
        - Lower latency for multiple API calls
        - Keep-alive headers for better performance
        
        Returns:
            requests.Session: Shared HTTP session instance
        """
        if self.http is None:
            self.http = requests.Session()
            try:
                self.http.headers.update({
                    "Connection": "keep-alive",
                    "User-Agent": "AstroRemedis-Bot/2.1.0"
                })
                # Optimized connection pooling for 14 parallel requests
                adapter = requests.adapters.HTTPAdapter(
                    pool_connections=20,  # Increased for more parallel connections
                    pool_maxsize=40,      # Increased pool size
                    max_retries=2,        # Reduced retries for faster failure
                    pool_block=False       # Don't block if pool is full
                )
                self.http.mount('http://', adapter)
                self.http.mount('https://', adapter)
            except Exception:
                pass
        return self.http
    
    def _generate_cache_key(self, dob_date, tob_time, latitude, longitude, timezone_str):
        """Generate a unique cache key for chart data based on birth parameters"""
        # Create a deterministic hash from birth parameters
        key_string = f"{dob_date.isoformat()}|{tob_time.isoformat()}|{latitude:.6f}|{longitude:.6f}|{timezone_str}"
        return sha256(key_string.encode()).hexdigest()[:16]  # Use first 16 chars for shorter keys
    
    def _get_cached_chart(self, cache_key):
        """Get cached chart data if available"""
        with self._chart_cache_lock:
            return self._chart_cache.get(cache_key)
    
    def _set_cached_chart(self, cache_key, chart_data):
        """Cache chart data with LRU eviction"""
        with self._chart_cache_lock:
            # If cache is full, remove oldest entry (simple FIFO)
            if len(self._chart_cache) >= self._chart_cache_max_size:
                # Remove first (oldest) item
                oldest_key = next(iter(self._chart_cache))
                del self._chart_cache[oldest_key]
            self._chart_cache[cache_key] = chart_data

    def __init__(self):
        """
        Initializes the AstroBot API components.
        Merged initialization logic from two previous, conflicting __init__ blocks.
        """
        # Essential instance attributes for core functionality
        self.http = None        # Reuse HTTP session for connection pooling
        self._geo_cache = {}    # Simple in-memory cache for geocoding results
        
        # ProKerala API access attributes
        self.access_token = None
        self.token_expiry = None
        
        # Chart data cache (LRU cache for repeated requests)
        self._chart_cache = {}  # Key: hash of birth params, Value: chart data
        self._chart_cache_lock = threading.Lock()  # Thread-safe cache access
        self._chart_cache_max_size = 100  # Maximum cached charts
        
        # Request deduplication (prevent duplicate concurrent requests for same chart)
        # Key: request hash, Value: Future object
        self._pending_requests = {}
        self._pending_requests_lock = threading.Lock()
        
        # Note: Vector store initialization removed - using OpenAI Assistant API instead

    def get_access_token(self, retry_count=3):
        """
        Get access token from ProKerala API with caching, retry logic, and error handling.
        
        Token is cached for 1 hour to avoid unnecessary API calls.
        If token is expired or missing, requests a new one with retry logic.
        
        Args:
            retry_count (int): Number of retry attempts (default: 3)
        
        Returns:
            str: Access token if successful, None otherwise
        """
        # Check if credentials are set (not just truthy, but actually have content)
        client_id = PROKERALA_CLIENT_ID and str(PROKERALA_CLIENT_ID).strip()
        client_secret = PROKERALA_CLIENT_SECRET and str(PROKERALA_CLIENT_SECRET).strip()
        
        logger.info(f"PROKERALA_CLIENT_ID set: {bool(client_id)}")
        logger.info(f"PROKERALA_CLIENT_SECRET set: {bool(client_secret)}")

        if not client_id or not client_secret:
            logger.error("ProKerala credentials not found in environment variables")
            logger.error("Please check PROKERALA_CLIENT_ID and PROKERALA_CLIENT_SECRET in environment variables")
            return None

        # Return cached token if still valid
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            logger.debug("Using cached ProKerala access token")
            return self.access_token

        token_url = "https://api.prokerala.com/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }

        # Retry logic with exponential backoff
        import time
        last_exception = None
        
        for attempt in range(retry_count):
            try:
                logger.info(f"Requesting ProKerala token (attempt {attempt + 1}/{retry_count})...")
                
                # Use longer timeout for production environments (Render, etc.)
                timeout = 30 if os.getenv('RENDER') or os.getenv('DYNO') else 15
                
                response = self._get_http().post(
                    token_url, 
                    data=data, 
                    timeout=timeout,
                    headers={'User-Agent': 'AstroRemedis-Bot/2.1.0'}
                )

                # Enhanced Authentication Error Check
                if response.status_code in [400, 401]:
                    error_details = response.json().get('error_description', response.text) if response.text else 'Unknown error'
                    logger.error(f"ProKerala AUTH Failed (Status: {response.status_code}). Details: {error_details}")
                    # Don't retry on auth errors
                    return None

                response.raise_for_status()
                token_data = response.json()
                
                if 'access_token' not in token_data:
                    logger.error(f"ProKerala response missing access_token: {token_data}")
                    return None
                
                self.access_token = token_data["access_token"]
                # Set expiry time (assuming 1 hour token validity, but use actual expiry if provided)
                expires_in = token_data.get('expires_in', 3600)  # Default to 1 hour
                self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)  # 1 minute buffer
                
                logger.info("Successfully obtained ProKerala access token")
                return self.access_token

            except requests.exceptions.ConnectionError as e:
                last_exception = e
                error_msg = str(e)
                if 'Connection reset' in error_msg or '104' in error_msg:
                    logger.warning(f"Connection reset during ProKerala token request (attempt {attempt + 1}/{retry_count}): {e}")
                else:
                    logger.warning(f"Connection error during ProKerala token request (attempt {attempt + 1}/{retry_count}): {e}")
                
                if attempt < retry_count - 1:
                    # Exponential backoff: 2^attempt seconds
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to get ProKerala token after {retry_count} attempts")
                    
            except requests.exceptions.Timeout as e:
                last_exception = e
                logger.warning(f"Timeout during ProKerala token request (attempt {attempt + 1}/{retry_count}): {e}")
                if attempt < retry_count - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Timeout getting ProKerala token after {retry_count} attempts")
                    
            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.error(f"Network Error during ProKerala token request (attempt {attempt + 1}/{retry_count}): {e}")
                if attempt < retry_count - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Network error getting ProKerala token after {retry_count} attempts")
                    
            except Exception as e:
                last_exception = e
                logger.error(f"Unknown Error during ProKerala token request (attempt {attempt + 1}/{retry_count}): {e}")
                import traceback
                logger.error(traceback.format_exc())
                # Don't retry on unknown errors (likely code issues)
                break
        
        # All retries failed
        logger.error(f"Failed to get ProKerala access token after {retry_count} attempts. Last error: {last_exception}")
        return None

    def get_coordinates(self, place_name):
        """
        Get latitude/longitude for a place name with caching.
        
        Uses geocoding cache to avoid repeated API calls for the same place.
        Falls back to Mumbai coordinates if geocoding fails.
        
        Args:
            place_name (str): Name of the place/city
            
        Returns:
            tuple: (latitude, longitude) coordinates
        """
        if not place_name:
            return DEFAULT_LAT, DEFAULT_LON

        # Return from cache if available
        cached = self._geo_cache.get(place_name.lower())
        if cached:
            return cached

        geolocator = Nominatim(user_agent="astrobot_app")
        try:
            location = geolocator.geocode(place_name, timeout=8)
            if location:
                coords = (location.latitude, location.longitude)
                # Cache for future use
                self._geo_cache[place_name.lower()] = coords
                return coords
        except Exception as e:
            logger.warning(f"Geocoding failed for '{place_name}': {e}")
        return DEFAULT_LAT, DEFAULT_LON  # Fallback to Mumbai

    # Mock data generation removed; real API data is required

    def _fetch_planet_positions(self, base_url, headers, common_params):
        """Helper method to fetch planet positions"""
        try:
            planets_url = f"{base_url}/planet-position"
            planets_response = self._get_http().get(planets_url, headers=headers, params=common_params, timeout=10)
            planets_response.raise_for_status()
            result = planets_response.json().get('data', {}).get('planet_position', [])
            logger.info("✅ Planet Positions fetched successfully")
            return ('planet_positions', result)
        except Exception as e:
            logger.error(f"Error fetching Planet Positions: {e}")
            return ('planet_positions', [])

    def _fetch_kundli(self, base_url, headers, common_params):
        """Helper method to fetch advanced Kundli"""
        try:
            kundli_url = f"{base_url}/kundli/advanced"
            kundli_response = self._get_http().get(kundli_url, headers=headers, params=common_params, timeout=12)
            kundli_response.raise_for_status()
            result = kundli_response.json().get('data', {})
            logger.info("✅ Kundli Advanced fetched successfully")
            return ('kundli', result)
        except Exception as e:
            logger.error(f"Error fetching Kundli: {e}")
            return ('kundli', {})

    def _fetch_bhava_position(self, base_url, headers, common_params):
        """Helper method to fetch Bhava positions"""
        try:
            bhava_url = f"{base_url}/bhava-position"
            bhava_response = self._get_http().get(bhava_url, headers=headers, params=common_params, timeout=10)
            bhava_response.raise_for_status()
            result = bhava_response.json().get('data', {}).get('bhava_position', [])
            logger.info("✅ Bhava Positions fetched successfully")
            return ('bhava_position', result)
        except Exception as e:
            logger.error(f"Error fetching Bhava Positions: {e}")
            return ('bhava_position', [])

    def _fetch_mangal_dosha(self, base_url, headers, common_params):
        """Helper method to fetch Mangal Dosha"""
        try:
            mangal_url = f"{base_url}/mangal-dosha"
            mangal_response = self._get_http().get(mangal_url, headers=headers, params=common_params, timeout=12)
            mangal_response.raise_for_status()
            result = mangal_response.json().get('data', {})
            logger.info("✅ Mangal Dosha fetched successfully")
            return ('mangal_dosha', result)
        except Exception as e:
            logger.error(f"Error fetching Mangal Dosha: {e}")
            return ('mangal_dosha', {})

    def _fetch_yoga(self, base_url, headers, common_params):
        """Helper method to fetch Auspicious Yoga"""
        try:
            yoga_url = f"{base_url}/auspicious-yoga"
            yoga_response = self._get_http().get(yoga_url, headers=headers, params=common_params, timeout=12)
            yoga_response.raise_for_status()
            result = yoga_response.json().get('data', {})
            logger.info("✅ Auspicious Yoga fetched successfully")
            return ('yoga', result)
        except Exception as e:
            logger.error(f"Error fetching Auspicious Yoga: {e}")
            return ('yoga', {})

    def _fetch_sade_sati(self, base_url, headers, common_params):
        """Helper method to fetch Sade Sati"""
        try:
            sade_sati_url = f"{base_url}/sade-sati"
            sade_sati_response = self._get_http().get(sade_sati_url, headers=headers, params=common_params, timeout=12)
            sade_sati_response.raise_for_status()
            result = sade_sati_response.json().get('data', {})
            logger.info("✅ Sade Sati fetched successfully")
            return ('sade_sati', result)
        except Exception as e:
            logger.error(f"Error fetching Sade Sati: {e}")
            return ('sade_sati', {})

    def _fetch_chart(self, base_url, headers, timezone_str, dob_date, tob_time, latitude, longitude):
        """Helper method to fetch visual chart (SVG)"""
        try:
            # Prepare datetime for chart endpoint (needs specific format)
            local_tz = pytz.timezone(timezone_str)
            birth_datetime = datetime.combine(dob_date, tob_time)
            local_datetime = local_tz.localize(birth_datetime)
            chart_datetime_str = local_datetime.strftime('%Y-%m-%dT%H:%M:%S%z')
            if chart_datetime_str.endswith('+0000'):
                chart_datetime_str = chart_datetime_str.replace('+0000', 'Z')
            elif '+' in chart_datetime_str:
                chart_datetime_str = chart_datetime_str[:-2] + ':' + chart_datetime_str[-2:]
            
            chart_url = f"{base_url}/chart"
            chart_params = {
                'ayanamsa': 5,  # KP Astrology
                'coordinates': f"{latitude},{longitude}",
                'datetime': chart_datetime_str,
                'chart_type': 'rasi',
                'chart_style': 'north-indian',
                'format': 'svg'
            }
            
            chart_response = self._get_http().get(chart_url, headers=headers, params=chart_params, timeout=15)
            chart_response.raise_for_status()
            
            # Check if response is SVG
            content_type = chart_response.headers.get('content-type', '')
            if 'svg' in content_type or chart_response.text.strip().startswith('<svg'):
                result = {
                    'svg_content': chart_response.text,
                    'format': 'svg',
                    'chart_type': 'north-indian',
                    'ayanamsa': 5,
                    'astrology_system': 'KP'
                }
                logger.info("✅ Chart SVG fetched successfully from ProKerala Chart endpoint")
                return ('chart', result)
            else:
                # Fallback to JSON if not SVG
                chart_json = chart_response.json().get('data', {})
                result = {
                    'chart_data': chart_json,
                    'format': 'json',
                    'chart_type': 'north-indian',
                    'ayanamsa': 5,
                    'astrology_system': 'KP'
                }
                logger.info("✅ Chart data fetched successfully (JSON format) from ProKerala Chart endpoint")
                return ('chart', result)
        except Exception as e:
            logger.error(f"Error fetching Chart from ProKerala Chart endpoint: {e}")
            return ('chart', {})

    def _fetch_kaal_sarp_dosha(self, base_url, headers, common_params):
        """Helper method to fetch Kaal Sarp Dosha"""
        try:
            kaal_sarp_url = f"{base_url}/kaal-sarp-dosha"
            kaal_sarp_response = self._get_http().get(kaal_sarp_url, headers=headers, params=common_params, timeout=12)
            kaal_sarp_response.raise_for_status()
            result = kaal_sarp_response.json().get('data', {})
            logger.info("✅ Kaal Sarp Dosha fetched successfully")
            return ('kaal_sarp_dosha', result)
        except Exception as e:
            logger.error(f"Error fetching Kaal Sarp Dosha: {e}")
            return ('kaal_sarp_dosha', {})

    def _fetch_upagraha_position(self, base_url, headers, common_params):
        """Helper method to fetch Upagraha positions"""
        try:
            upagraha_url = f"{base_url}/upagraha-position"
            upagraha_response = self._get_http().get(upagraha_url, headers=headers, params=common_params, timeout=10)
            upagraha_response.raise_for_status()
            result = upagraha_response.json().get('data', {}).get('upagraha', [])
            logger.info("✅ Upagraha Positions fetched successfully")
            return ('upagraha_position', result)
        except Exception as e:
            logger.error(f"Error fetching Upagraha Positions: {e}")
            return ('upagraha_position', [])

    def _fetch_yoga_general(self, base_url, headers, common_params):
        """Helper method to fetch general Yoga (different from auspicious-yoga)"""
        try:
            yoga_url = f"{base_url}/yoga"
            yoga_response = self._get_http().get(yoga_url, headers=headers, params=common_params, timeout=12)
            yoga_response.raise_for_status()
            result = yoga_response.json().get('data', {})
            logger.info("✅ Yoga (general) fetched successfully")
            return ('yoga_general', result)
        except Exception as e:
            logger.error(f"Error fetching Yoga (general): {e}")
            return ('yoga_general', {})

    def _fetch_dasha_periods(self, base_url, headers, common_params):
        """Helper method to fetch Dasha periods"""
        try:
            dasha_url = f"{base_url}/dasha-periods"
            dasha_response = self._get_http().get(dasha_url, headers=headers, params=common_params, timeout=10)
            dasha_response.raise_for_status()
            result = dasha_response.json().get('data', {})
            logger.info("✅ Dasha Periods fetched successfully")
            return ('dasha_periods', result)
        except Exception as e:
            logger.error(f"Error fetching Dasha Periods: {e}")
            return ('dasha_periods', {})

    def _fetch_planet_relationship(self, base_url, headers, common_params):
        """Helper method to fetch Planet relationships"""
        try:
            planet_rel_url = f"{base_url}/planet-relationship"
            planet_rel_response = self._get_http().get(planet_rel_url, headers=headers, params=common_params, timeout=10)
            planet_rel_response.raise_for_status()
            result = planet_rel_response.json().get('data', {})
            logger.info("✅ Planet Relationships fetched successfully")
            return ('planet_relationship', result)
        except Exception as e:
            logger.error(f"Error fetching Planet Relationships: {e}")
            return ('planet_relationship', {})

    def _fetch_divisional_planet_position(self, base_url, headers, common_params):
        """Helper method to fetch Divisional planet positions"""
        try:
            divisional_url = f"{base_url}/divisional-planet-position"
            divisional_response = self._get_http().get(divisional_url, headers=headers, params=common_params, timeout=10)
            divisional_response.raise_for_status()
            result = divisional_response.json().get('data', {})
            logger.info("✅ Divisional Planet Positions fetched successfully")
            return ('divisional_planet_position', result)
        except Exception as e:
            logger.error(f"Error fetching Divisional Planet Positions: {e}")
            return ('divisional_planet_position', {})

    def _fetch_chandrashtama_periods(self, base_url, headers, common_params):
        """Helper method to fetch Chandrashtama periods"""
        try:
            chandrashtama_url = f"{base_url}/chandrashtama-periods"
            chandrashtama_response = self._get_http().get(chandrashtama_url, headers=headers, params=common_params, timeout=12)
            chandrashtama_response.raise_for_status()
            result = chandrashtama_response.json().get('data', {})
            logger.info("✅ Chandrashtama Periods fetched successfully")
            return ('chandrashtama_periods', result)
        except Exception as e:
            logger.error(f"Error fetching Chandrashtama Periods: {e}")
            return ('chandrashtama_periods', {})

    def calculate_chart_data(self, name, dob_date, tob_time, pob_text, latitude, longitude, timezone_str):
        """
        Calculate comprehensive chart data by calling all ProKerala endpoints.
        
        This is the main function that orchestrates data fetching from:
        1. Planet positions
        2. Advanced Kundli data
        3. Bhava (house) positions
        4. Mangal Dosha analysis
        5. Auspicious Yoga
        6. Sade Sati analysis
        7. Visual SVG chart
        8. Kaal Sarp Dosha
        9. Upagraha positions
        10. General Yoga
        11. Dasha periods
        12. Planet relationships
        13. Divisional planet positions
        14. Chandrashtama periods
        
        All endpoints are called in parallel for optimal performance with proper error handling.
        Data is normalized to handle inconsistent API response shapes.
        Uses caching to avoid redundant API calls for same birth parameters.
        
        Args:
            name (str): Person's name
            dob_date (date): Date of birth
            tob_time (time): Time of birth
            pob_text (str): Place of birth
            latitude (float): Latitude coordinate
            longitude (float): Longitude coordinate
            timezone_str (str): Timezone string (e.g., 'Asia/Kolkata')
            
        Returns:
            dict: Comprehensive chart data with all ProKerala API responses
        """
        # Check cache first (chart data is deterministic based on birth parameters)
        cache_key = self._generate_cache_key(dob_date, tob_time, latitude, longitude, timezone_str)
        cached_data = self._get_cached_chart(cache_key)
        if cached_data:
            # Update name in cached data (only thing that might differ)
            cached_data['name'] = name
            cached_data['birth_location'] = pob_text
            logger.info("✅ Returning cached chart data")
            return cached_data
        
        # Check for duplicate concurrent request (simplified approach)
        # Note: For production, consider using a proper async framework or Redis for distributed caching
        access_token = self.get_access_token(retry_count=3)
        if not access_token:
            logger.error("ProKerala API credentials not available; cannot fetch chart data")
            logger.error("Please check PROKERALA_CLIENT_ID and PROKERALA_CLIENT_SECRET in environment variables")
            logger.error("If on Render, ensure these are set in the Render dashboard under Environment Variables")
            raise ValueError("ProKerala API credentials not configured or connection failed. Please check your environment variables and network connection.")

        try:
            # Create localized datetime
            local_tz = pytz.timezone(timezone_str)
            birth_datetime = datetime.combine(dob_date, tob_time)
            localized_dt = local_tz.localize(birth_datetime)

            # Use RAW ISO format string
            api_datetime_str = localized_dt.isoformat()

        except Exception as e:
            logger.error(f"Timezone or Date/Time Error: {e}")
            return None

        headers = {"Authorization": f"Bearer {access_token}"}
        base_url = "https://api.prokerala.com/v2/astrology"

        common_params = {
            'ayanamsa': 5,  # KP Astrology (Krishnamurti Paddhati)
            'coordinates': f"{latitude},{longitude}",
            'datetime': api_datetime_str,
            'chart_style': 'north-indian'  # North Indian chart style
        }

        # Initialize data containers
        api_data = {
            'planet_positions': [],
            'mangal_dosha': {},
            'kundli': {},
            'chart': {},
            'yoga': {},
            'dasha_periods': {},
            'sade_sati': {},
            'bhava_position': [],
            'kaal_sarp_dosha': {},
            'upagraha_position': [],
            'yoga_general': {},
            'planet_relationship': {},
            'divisional_planet_position': {},
            'chandrashtama_periods': {}
        }

        # Parallel fetch all ProKerala endpoints for better performance
        # Note: Chart endpoint needs special datetime format, so it's handled separately
        logger.info("🚀 Starting parallel fetch of ProKerala API endpoints...")
        with ThreadPoolExecutor(max_workers=14) as executor:
            # Submit all API calls except chart (which needs special formatting)
            futures = {
                executor.submit(self._fetch_planet_positions, base_url, headers, common_params): 'planet_positions',
                executor.submit(self._fetch_kundli, base_url, headers, common_params): 'kundli',
                executor.submit(self._fetch_bhava_position, base_url, headers, common_params): 'bhava_position',
                executor.submit(self._fetch_mangal_dosha, base_url, headers, common_params): 'mangal_dosha',
                executor.submit(self._fetch_yoga, base_url, headers, common_params): 'yoga',
                executor.submit(self._fetch_sade_sati, base_url, headers, common_params): 'sade_sati',
                executor.submit(self._fetch_kaal_sarp_dosha, base_url, headers, common_params): 'kaal_sarp_dosha',
                executor.submit(self._fetch_upagraha_position, base_url, headers, common_params): 'upagraha_position',
                executor.submit(self._fetch_yoga_general, base_url, headers, common_params): 'yoga_general',
                executor.submit(self._fetch_dasha_periods, base_url, headers, common_params): 'dasha_periods',
                executor.submit(self._fetch_planet_relationship, base_url, headers, common_params): 'planet_relationship',
                executor.submit(self._fetch_divisional_planet_position, base_url, headers, common_params): 'divisional_planet_position',
                executor.submit(self._fetch_chandrashtama_periods, base_url, headers, common_params): 'chandrashtama_periods',
            }
            
            # Collect results as they complete
            for future in as_completed(futures):
                key = futures[future]
                try:
                    result_key, result_value = future.result()
                    api_data[result_key] = result_value
                except Exception as e:
                    logger.error(f"Unexpected error processing {key}: {e}")
                    # Use empty defaults based on key type
                    if key in ['planet_positions', 'bhava_position', 'upagraha_position']:
                        api_data[key] = []
                    else:
                        api_data[key] = {}

        # Fetch chart separately (needs special datetime formatting)
        chart_key, chart_value = self._fetch_chart(base_url, headers, timezone_str, dob_date, tob_time, latitude, longitude)
        api_data[chart_key] = chart_value

        # Apply fallbacks for failed endpoints
        if not api_data.get('mangal_dosha'):
            api_data['mangal_dosha'] = api_data.get('kundli', {}).get('mangal_dosha', {})
        if not api_data.get('yoga'):
            api_data['yoga'] = api_data.get('kundli', {}).get('yoga_details', [])
        if not api_data.get('sade_sati'):
            api_data['sade_sati'] = api_data.get('kundli', {}).get('sade_sati', {})
        
        # Chart fallback if it failed
        if not api_data.get('chart'):
            try:
                kundli_data = api_data.get('kundli', {})
                api_data['chart'] = {
                    'kundli_data': kundli_data,
                    'format': 'json',
                    'chart_type': 'north-indian',
                    'ayanamsa': 5,
                    'astrology_system': 'KP'
                }
                logger.info("✅ Chart data extracted from Kundli as fallback")
            except Exception as fallback_error:
                logger.error(f"Error in chart fallback: {fallback_error}")
                api_data['chart'] = {}

        # Critical check: planet positions are required for chart calculation
        if not api_data.get('planet_positions'):
            logger.error("Planet positions are required but could not be fetched")
            logger.error("This usually means ProKerala API call failed. Check API credentials and network connection.")
            raise ValueError("Failed to fetch planet positions from ProKerala API. Please check API credentials and try again.")

        # Process Data into CHART_DATA format
        planets_in_house = {}
        ascendant_sign = None
        ascendant_sign_name = "N/A"

        planet_code_map = {
            'Sun': 'Su', 'Moon': 'Mo', 'Mars': 'Ma', 'Mercury': 'Me',
            'Jupiter': 'Ju', 'Venus': 'Ve', 'Saturn': 'Sa',
            'Rahu': 'Ra', 'Ketu': 'Ke', 'Lagna': 'La'
        }

        # Find Lagna/Ascendant
        lagna_planet = next((p for p in api_data['planet_positions'] if p.get('id') == 100), None)
        if lagna_planet:
            ascendant_sign = lagna_planet.get('rasi', {}).get('id')
            ascendant_sign_name = lagna_planet.get('rasi', {}).get('name')

        # Map Planets to Houses using Bhava Positions if available; fallback to rasi-based
        # Optimized: Pre-build bhava_map once and use it efficiently
        bhava_map = {}
        for p in api_data.get('bhava_position', []):
            pid = p.get('id')
            if pid is not None:
                bhava = p.get('bhava')
                if isinstance(bhava, int) and bhava > 0:
                    bhava_map[pid] = bhava
        
        # Optimized planet-to-house mapping
        if api_data['planet_positions']:
            for planet in api_data['planet_positions']:
                planet_id = planet.get('id')
                planet_name = planet.get('name')
                house_num = None
                
                # Try bhava_map first (faster lookup)
                if planet_id in bhava_map:
                    house_num = bhava_map[planet_id]
                elif ascendant_sign is not None:
                    sign_id = planet.get('rasi', {}).get('id')
                    if isinstance(sign_id, int):
                        house_num = (sign_id - ascendant_sign + 12) % 12 + 1

                if house_num is not None:
                    planet_code = planet_code_map.get(planet_name)
                    if not planet_code:
                        planet_code = (planet_name or '')[:2]
                    
                    if house_num not in planets_in_house:
                        planets_in_house[house_num] = []
                    if planet_code and planet_code not in planets_in_house[house_num]:
                        planets_in_house[house_num].append(planet_code)
        # Final CHART_DATA Structure with comprehensive ProKerala data
        final_chart_data = {
            "name": name,
            "dob_date": dob_date.strftime('%Y-%m-%d'),
            "tob_time": tob_time.strftime('%H:%M:%S'),
            "ascendant_sign": ascendant_sign or 1,
            "ascendant_sign_name": ascendant_sign_name,
            "planets": planets_in_house,
            "birth_location": pob_text,
            "coordinates": {
                "latitude": latitude,
                "longitude": longitude
            },
            "timezone": timezone_str,

            # ProKerala API Data
            "prokerala_data": {
                "kundli": api_data['kundli'],
                "chart": api_data['chart'],
                "planet_positions": api_data['planet_positions'],
                "bhava_position": api_data.get('bhava_position', []),
                "mangal_dosha": api_data.get('mangal_dosha', {}),
                "auspicious_yoga": api_data.get('yoga', {}),
                "sade_sati": api_data.get('sade_sati', {}),
                "kaal_sarp_dosha": api_data.get('kaal_sarp_dosha', {}),
                "upagraha_position": api_data.get('upagraha_position', []),
                "yoga_general": api_data.get('yoga_general', {}),
                "dasha_periods": api_data.get('dasha_periods', {}),
                "planet_relationship": api_data.get('planet_relationship', {}),
                "divisional_planet_position": api_data.get('divisional_planet_position', {}),
                "chandrashtama_periods": api_data.get('chandrashtama_periods', {})
            },
            
            # Visual Chart SVG (from ProKerala Chart endpoint)
            "visual_chart": api_data.get('chart', {}).get('svg_content') if api_data.get('chart', {}).get('format') == 'svg' else None,

            # Chart Configuration
            "chart_config": {
                "ayanamsa": 5,
                "chart_style": "north-indian",
                "astrology_system": "KP"
            },

            # Data from separate ProKerala API endpoints
            "mangal_dosha": api_data.get('mangal_dosha', {}),
            "dasha_periods": api_data.get('dasha_periods', {}) or api_data.get('kundli', {}).get('dasha_periods', {}),
            "sade_sati": api_data.get('sade_sati', {}),
            "yoga": api_data.get('yoga', {}),
            "kaal_sarp_dosha": api_data.get('kaal_sarp_dosha', {}),
            "upagraha_position": api_data.get('upagraha_position', []),
            "yoga_general": api_data.get('yoga_general', {}),
            "planet_relationship": api_data.get('planet_relationship', {}),
            "divisional_planet_position": api_data.get('divisional_planet_position', {}),
            "chandrashtama_periods": api_data.get('chandrashtama_periods', {})
        }

        return final_chart_data

    def generate_chart_only(self, name, dob_date, tob_time, pob_text, latitude, longitude, timezone_str):
        """Generate only the visual chart using ProKerala chart endpoint"""
        access_token = self.get_access_token()
        logger.info(f"Access token status: {'Available' if access_token else 'Not available'}")

        # Require real API; do not generate mock charts
        if not access_token:
            logger.error("ProKerala API credentials not available; cannot generate chart")
            return None

        try:
            # Create localized datetime
            local_tz = pytz.timezone(timezone_str)
            birth_datetime = datetime.combine(dob_date, tob_time)
            local_datetime = local_tz.localize(birth_datetime)
            api_datetime_str = local_datetime.strftime('%Y-%m-%dT%H:%M:%S%z')
            if api_datetime_str.endswith('+0000'):
                api_datetime_str = api_datetime_str.replace('+0000', 'Z')
            elif '+' in api_datetime_str:
                api_datetime_str = api_datetime_str[:-2] + ':' + api_datetime_str[-2:]

            logger.info(f"API DateTime: {api_datetime_str}")
            logger.info(f"Coordinates: {latitude}, {longitude}")

            headers = {"Authorization": f"Bearer {access_token}"}
            base_url = "https://api.prokerala.com/v2/astrology"

            # Use ProKerala Chart endpoint (SVG format)
            try:
                chart_params = {
                    'ayanamsa': 5,  # KP Astrology
                    'coordinates': f"{latitude},{longitude}",
                    'datetime': api_datetime_str,
                    'chart_type': 'rasi',  # Simple string value as per API docs
                    'chart_style': 'north-indian',
                    'format': 'svg'
                }

                logger.info(f"Chart URL: {base_url}/chart")
                logger.info(f"Chart Params: {chart_params}")

                chart_url = f"{base_url}/chart"
                chart_response = self._get_http().get(chart_url, headers=headers, params=chart_params, timeout=15)

                logger.info(f"Chart Response Status: {chart_response.status_code}")
                logger.info(f"Chart Response Content-Type: {chart_response.headers.get('content-type', '')}")

                if chart_response.status_code != 200:
                    logger.error(f"Chart API Error: {chart_response.text}")
                    return None

                # Check if response is SVG
                content_type = chart_response.headers.get('content-type', '')
                if 'svg' in content_type:
                    chart_data = {
                        'svg_content': chart_response.text,
                        'format': 'svg',
                        'chart_type': 'north-indian',
                        'ayanamsa': 5,
                        'astrology_system': 'KP'
                    }
                    logger.info("✅ SVG Chart fetched successfully from ProKerala Chart endpoint")
                    return chart_data
                else:
                    # Fallback to JSON response
                    chart_data = chart_response.json().get('data', {})
                    chart_data.update({
                        'format': 'json',
                        'chart_type': 'north-indian',
                        'ayanamsa': 5,
                        'astrology_system': 'KP'
                    })
                    logger.info("✅ Chart data fetched successfully (JSON format) from ProKerala Chart endpoint")
                    return chart_data
            except Exception as e:
                logger.error(f"Error fetching Chart from ProKerala Chart endpoint: {e}")
                return None

        except Exception as e:
            logger.error(f"Timezone or Date/Time Error: {e}")
            return None

    # Mock chart generation removed

    def _get_basic_ai_response(self, question, chart_data):
        """Disabled: Do not generate predictions locally; require Assistant API."""
        return "AI assistant is not configured. Please try again later."

    def get_rag_response(self, question, chart_data, conversation_history=None, assistant_id_override: str = None, thread_id=None):
        """
        Get AI response using OpenAI Assistant API.
        
        This method:
        1. Selects the appropriate Assistant (default or horary)
        2. Compacts chart data to avoid token limits
        3. Calculates age-based prediction logic
        4. Generates remedies if needed
        5. Creates follow-up questions based on query type
        6. Sends context to Assistant API
        7. Waits for response and returns it
        
        Args:
            question (str): User's question
            chart_data (dict): Kundli/chart data for context
            conversation_history (list, optional): Previous messages (not used currently)
            assistant_id_override (str, optional): Override default Assistant ID
            
        Returns:
            str: AI-generated response in Hindi/Hinglish
        """
        if not OPENAI_API_KEY:
            return "AI assistant is not configured. Please add OPENAI_API_KEY."
        
        # Choose assistant id (allow override per mode/use-case)
        selected_assistant_id = (assistant_id_override or OPENAI_ASSISTANT_ID)
        if not selected_assistant_id:
            logger.warning("OPENAI_ASSISTANT_ID not set")
            return "AI assistant is not configured. Please add OPENAI_ASSISTANT_ID."

        try:
            # Initialize OpenAI client
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            
            # Age calculation for realistic predictions
            dob_date_str = chart_data.get('dob_date')
            dob_date = datetime(2000, 1, 1).date() # Default if parsing fails
            
            if isinstance(dob_date_str, str):
                try:
                    # Assuming YYYY-MM-DD format from parse_birth_data and calculate_chart_data
                    dob_date = datetime.strptime(dob_date_str, '%Y-%m-%d').date()
                except:
                    pass # Keep default date

            # Get current year dynamically (not hardcoded)
            current_datetime = datetime.now()
            current_year = current_datetime.year
            birth_year = dob_date.year
            current_age = current_year - birth_year

            # Define minimum realistic ages for prediction categories
            min_ages = {
                "relationship_advice": 25,
                "career_guidance": 20,
                "health_guidance": 15,
                "child_guidance": 26,
                "general_astrology": 15
            }

            # Determine the context and required minimum age
            question_lower = question.lower()
            response_style = "general_astrology"
            # Initialize with a safe default so it's always defined
            earliest_marriage_year = birth_year + min_ages["relationship_advice"]
            logger.info(f"[AI] birth_year={birth_year}, default earliest_marriage_year={earliest_marriage_year}")

            if any(word in question_lower for word in ['love', 'marriage', 'relationship', 'shadi', 'pyaar', 'vivah']):
                response_style = "relationship_advice"
                earliest_marriage_year = birth_year + min_ages["relationship_advice"]
            elif any(word in question_lower for word in ['child', 'santan', 'baby', 'bacche']):
                response_style = "child_guidance"
            elif any(word in question_lower for word in ['career', 'job', 'profession', 'work', 'rozi', 'naukri']):
                response_style = "career_guidance"
            elif any(word in question_lower for word in ['health', 'swasthya', 'illness', 'disease']):
                response_style = "health_guidance"

            # Calculate realistic prediction timing
            minimum_age_threshold = min_ages.get(response_style, 15)
            earliest_realistic_year = birth_year + minimum_age_threshold

            if response_style == "child_guidance":
                min_child_start_year = earliest_marriage_year + 1
                minimum_age_threshold = min_child_start_year - birth_year
                earliest_realistic_year = min_child_start_year
                childbirth_logic_context = f"""
                **CHILD CHRONOLOGY RULE (NON-NEGOTIABLE):** The base prediction year for children is {min_child_start_year} (Age {minimum_age_threshold}), which is 1 year after the earliest possible realistic marriage year ({earliest_marriage_year}). YOU MUST NOT PREDICT ANY CHILDBIRTH EVENT BEFORE {min_child_start_year}.
                """
            else:
                childbirth_logic_context = ""

            # Age/Logic context for the AI
            age_logic_context = f"""
            **INTERNAL AGE/LOGIC CONTEXT:**
            User was born in {birth_year}. Current Age: {current_age}.
            **CURRENT YEAR: {current_year}** - All predictions must be for {current_year} onwards.
            Question Type: {response_style}.
            Minimum realistic age for this event is {minimum_age_threshold} years.
            Prediction year MUST be >= {earliest_realistic_year} AND >= {current_year}.
            If the Dasha data shows a favorable time before {earliest_realistic_year} or before {current_year}, IGNORE it and find the next favorable timing after {earliest_realistic_year} and {current_year}.
            {childbirth_logic_context}
            """

            # Build a compact chart context to reduce prompt size
            def build_compact_chart(src):
                try:
                    planets = src.get('planets') or {}
                    compact_planets = {}
                    for house, plist in planets.items():
                        # keep max 5 planet codes per house
                        compact_planets[str(house)] = (plist or [])[:5]

                    prokerala = src.get('prokerala_data') or {}
                    mangal = src.get('mangal_dosha') or prokerala.get('mangal_dosha') or {}

                    compact = {
                        'name': src.get('name') or 'User',
                        'dob_date': dob_date.strftime('%Y-%m-%d'),
                        'ascendant_sign': src.get('ascendant_sign'),
                        'ascendant_sign_name': src.get('ascendant_sign_name'),
                        'planets': compact_planets,
                        'mangal_dosha': {
                            'is_present': bool(mangal.get('is_present', mangal.get('has_dosha', False))),
                            'description': (mangal.get('description') or '')[:200]
                        },
                        'birth_location': src.get('birth_location'),
                        'coordinates': src.get('coordinates'),
                        'timezone': src.get('timezone'),
                        'chart_config': src.get('chart_config') or {
                            'ayanamsa': 5,
                            'chart_style': 'north-indian',
                            'astrology_system': 'KP'
                        },
                        'summary': {
                            'has_chart_svg': bool((src or {}).get('svg_content')),
                            'has_prokerala': bool(prokerala)
                        }
                    }
                    return compact
                except Exception:
                    return {'name': src.get('name', 'User')}

            # Build compact chart with enhanced compaction for Assistant API
            compact_chart = build_compact_chart(chart_data or {})
            
            # Add dasha periods, yoga, and sade sati if available (compacted)
            if chart_data:
                # Extract dasha periods (limit to first 3)
                dasha_periods = chart_data.get('dasha_periods', {})
                if isinstance(dasha_periods, list):
                    compact_chart['dasha_periods'] = dasha_periods[:3]
                elif isinstance(dasha_periods, dict):
                    compact_chart['dasha_periods'] = dict(list(dasha_periods.items())[:3])
                
                # Extract yoga (limit and truncate)
                yoga = chart_data.get('yoga', {})
                if isinstance(yoga, dict) and 'yoga_details' in yoga:
                    yoga_details = yoga.get('yoga_details', [])
                    if isinstance(yoga_details, list):
                        compact_yoga = []
                        for y in yoga_details[:5]:
                            if isinstance(y, dict):
                                compact_y = {k: (v[:100] if isinstance(v, str) and len(v) > 100 else v) 
                                             for k, v in y.items()}
                                compact_yoga.append(compact_y)
                        compact_chart['yoga'] = {'yoga_details': compact_yoga}
                
                # Extract sade sati (essential fields only)
                sade_sati = chart_data.get('sade_sati', {})
                if isinstance(sade_sati, dict):
                    compact_chart['sade_sati'] = {
                        'is_in_sade_sati': sade_sati.get('is_in_sade_sati', False),
                        'phase': sade_sati.get('phase', ''),
                        'description': (sade_sati.get('description') or '')[:200]
                    }
            
            chart_context = json.dumps(compact_chart, ensure_ascii=False, indent=1)
            # Limit chart context to 20000 characters for Assistant API
            if len(chart_context) > 20000:
                chart_context = chart_context[:20000] + "\n... (truncated for length)"

            # Context-aware follow-up questions based on the user's question
            # Select appropriate follow-up question based on response style
            follow_up_instruction = ""
            # Combined logic: if it's one of the targeted advice categories
            if response_style in ["relationship_advice", "career_guidance", "health_guidance", "child_guidance"]:
                import random
                import time

                # Map response styles to follow-up categories using config
                follow_up_category = RESPONSE_STYLE_MAP.get(response_style, "general")

                # Use current time to ensure different questions each time
                random.seed(int(time.time()) % 1000)
                follow_up_question = random.choice(FOLLOW_UP_QUESTIONS[follow_up_category])

                # Add variety in question introduction using config
                intro = random.choice(QUESTION_INTROS)
                follow_up_instruction = f"{intro} '{follow_up_question}'"

            # Build remedies section only if the question implies a problem/pain
            remedies_section = generate_remedies(question, chart_data, compact=True) if should_append_remedies(question) else ""

            safe_earliest_marriage_year = earliest_marriage_year or (birth_year + min_ages["relationship_advice"])
            logger.info(f"[AI] response_style={response_style}, earliest_realistic_year={earliest_realistic_year}, earliest_marriage_year={safe_earliest_marriage_year}")

            # Build the complete user message with context for Assistant API
            # Note: The Assistant is already configured with instructions, so we mainly need to provide context
            user_message_with_context = f"""
**User's Question:** "{question}"

**INTERNAL REFERENCE DATA (Analyze and Apply Rules):**
{chart_context}

{age_logic_context}

**ADDITIONAL INSTRUCTIONS:**
{('MANDATORY: You MUST include these EXACT remedies in your response as plain text (copy them exactly, including the natural empathetic introduction): ' + remedies_section) if remedies_section else ''}
{follow_up_instruction if follow_up_instruction else ''}

Please provide astrological guidance based on the above chart data and question, following all the rules configured in your system instructions.
            """.strip()
            
            # Final safety check - limit total message to 200000 characters (Assistant API limit is 256000)
            if len(user_message_with_context) > 200000:
                user_message_with_context = user_message_with_context[:200000] + "\n... (message truncated)"
            
            # Reuse existing thread if provided, otherwise create a new one
            # Skip verification API call - if thread is invalid, we'll handle it when adding message
            thread_id_to_use = thread_id if thread_id else None
            
            if not thread_id_to_use:
                # Create a new thread
                thread = client.beta.threads.create()
                thread_id_to_use = thread.id
                logger.debug(f"Created new thread: {thread_id_to_use}")
            else:
                logger.debug(f"Reusing existing thread: {thread_id_to_use}")
            
            # Add message to thread
            try:
                client.beta.threads.messages.create(
                    thread_id=thread_id_to_use,
                    role="user",
                    content=user_message_with_context
                )
            except Exception as e:
                logger.warning(f"Error adding message to thread {thread_id_to_use}: {e}")
                # If thread is invalid, create a new one
                thread = client.beta.threads.create()
                thread_id_to_use = thread.id
                logger.debug(f"Created new thread after error: {thread_id_to_use}")
                client.beta.threads.messages.create(
                    thread_id=thread_id_to_use,
                    role="user",
                    content=user_message_with_context
                )
            
            # Run assistant
            run = client.beta.threads.runs.create(
                thread_id=thread_id_to_use,
                assistant_id=selected_assistant_id
            )
            
            # Wait for completion
            import time
            max_wait_time = 60  # Maximum wait time in seconds
            start_time = time.time()
            
            while run.status in ['queued', 'in_progress', 'cancelling']:
                if time.time() - start_time > max_wait_time:
                    logger.error("Assistant API timeout")
                    return ("Sorry, main abhi thoda busy hun. Kripya thodi der baad try karein.", thread_id_to_use)
                
                time.sleep(0.5)  # Poll faster for quicker responses
                run = client.beta.threads.runs.retrieve(
                    thread_id=thread_id_to_use,
                    run_id=run.id
                )
            
            # Check if run completed successfully
            if run.status == 'completed':
                # Retrieve messages from the thread
                messages = client.beta.threads.messages.list(thread_id=thread_id_to_use)
                
                # Get the assistant's response (first message in the list should be the latest)
                assistant_messages = [msg for msg in messages.data if msg.role == 'assistant']
                if assistant_messages:
                    # Get the text content from the first assistant message
                    content = assistant_messages[0].content[0]
                    if hasattr(content, 'text'):
                        response_text = content.text.value
                        # Return tuple with response and thread_id for reuse
                        return (response_text, thread_id_to_use)
                    else:
                        return (str(content), thread_id_to_use)
                else:
                    return ("Sorry, main response generate nahi kar paya. Kripya dobara try karein.", thread_id_to_use)
            else:
                logger.error(f"Assistant run failed with status: {run.status}")
                if run.last_error:
                    logger.error(f"Error: {run.last_error}")
                # Return thread_id even on failure so it can be reused
                return ("Sorry, main abhi thoda busy hun. Kripya thodi der baad try karein.", thread_id_to_use)

        except Exception as e:
            logger.error(f"Error in Assistant API response: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Try to preserve thread_id if we have one
            preserved_thread_id = thread_id if thread_id else None
            return (f"Sorry, I encountered an error with the AI model: {e}", preserved_thread_id)

    # Note: generate_ai_response and _get_basic_response methods removed
    # All AI responses now go through get_rag_response() which uses OpenAI Assistant API

# ============================================================================
# Global API Instance
# ============================================================================
# Initialize the main API instance - this is used by all Flask routes
astro_api = EnhancedAstroBotAPI()

# ============================================================================
# Thread Management for Conversation Context
# ============================================================================
# Store OpenAI thread IDs per session to maintain conversation context across requests.
# This allows the AI to remember previous messages in the same conversation.
#
# Structure:
#   {
#     session_id: {
#       'thread_id': 'thread_xxx',  # OpenAI thread ID
#       'last_used': datetime,      # Last access timestamp
#       'created': datetime          # Creation timestamp
#     }
#   }
thread_store = {}
THREAD_STORE_MAX_AGE_HOURS = 24  # Clean up threads older than 24 hours

def _cleanup_old_threads():
    """
    Clean up old threads from thread_store.
    
    Removes threads that haven't been used in THREAD_STORE_MAX_AGE_HOURS.
    This prevents memory leaks from abandoned conversation threads.
    
    Called automatically during thread retrieval operations.
    """
    try:
        cutoff_time = datetime.now() - timedelta(hours=THREAD_STORE_MAX_AGE_HOURS)
        sessions_to_remove = [
            session_id for session_id, data in thread_store.items()
            if isinstance(data, dict) and data.get('last_used', datetime.now()) < cutoff_time
        ]
        for session_id in sessions_to_remove:
            del thread_store[session_id]
        if sessions_to_remove:
            logger.info(f"Cleaned up {len(sessions_to_remove)} old thread(s) from thread_store")
    except Exception as e:
        logger.warning(f"Error cleaning up old threads: {e}")

@app.route('/')
def home():
    """
    Home endpoint - API information and available endpoints.
    
    Returns:
        JSON: API version, features, and available endpoints
    """
    return jsonify({
        "message": "Enhanced AstroBot API is running!",
        "version": "2.1.0",
        "features": [
            "OpenAI Assistant API",
            "ProKerala API Integration",
            "Mangal Dosha Calculation",
            "Advanced AI Responses",
            "Timezone Support"
        ],
        "endpoints": {
            "chat": "/api/chat",
            "kundli": "/api/kundli",
            "analyze": "/api/analyze",
            "health": "/api/health",
            "restart": "/api/restart"
        }
    })

@app.route('/api/health')
def health_check():
    """
    Health check endpoint - Verify API status and configuration.
    
    Returns:
        JSON: Status, timestamp, and enabled features (Assistant API, ProKerala)
    """
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "features": {
            "assistant_api_enabled": OPENAI_API_KEY is not None and OPENAI_ASSISTANT_ID is not None,
            "openai_enabled": OPENAI_API_KEY is not None,
            "prokerala_enabled": PROKERALA_CLIENT_ID is not None
        }
    })

@app.route('/api/restart', methods=['POST'])
def restart_server():
    """
    Restart server endpoint - Triggers a restart of the backend server.
    
    For AWS Elastic Beanstalk: Uses boto3 to restart the environment.
    For local development: Provides instructions for manual restart.
    
    Optional Security:
    - Set RESTART_TOKEN environment variable to require authentication
    - If set, request must include 'token' in JSON body matching RESTART_TOKEN
    
    Request Body (optional):
        - token (str, optional): Restart token if RESTART_TOKEN is set
    
    Returns:
        JSON: Status message indicating restart initiation
    """
    try:
        # Optional security: Check for restart token
        restart_token = os.getenv('RESTART_TOKEN')
        if restart_token:
            data = request.get_json() or {}
            provided_token = data.get('token', '')
            if provided_token != restart_token:
                return jsonify({
                    "error": "Unauthorized",
                    "message": "Invalid restart token"
                }), 401
        
        # Try to restart using AWS Elastic Beanstalk (if boto3 is available)
        try:
            import boto3
            from botocore.exceptions import ClientError, BotoCoreError
            
            # Get environment name from EB environment variable or config
            eb_environment_name = os.getenv('AWS_EB_ENVIRONMENT_NAME')
            aws_region = os.getenv('AWS_REGION', 'eu-north-1')  # Default to your region
            
            if eb_environment_name:
                try:
                    # Initialize boto3 client
                    eb_client = boto3.client('elasticbeanstalk', region_name=aws_region)
                    
                    # Restart the application server (faster than full environment restart)
                    logger.info(f"Attempting to restart EB environment: {eb_environment_name}")
                    response = eb_client.restart_app_server(
                        EnvironmentName=eb_environment_name
                    )
                    
                    logger.info("Server restart initiated successfully via AWS EB")
                    return jsonify({
                        "status": "success",
                        "message": "Server restart initiated",
                        "method": "AWS Elastic Beanstalk",
                        "environment": eb_environment_name,
                        "timestamp": datetime.now().isoformat()
                    }), 200
                    
                except ClientError as e:
                    error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                    logger.warning(f"AWS EB restart failed: {error_code} - {str(e)}")
                    # Fall through to alternative methods
                except BotoCoreError as e:
                    logger.warning(f"AWS SDK error: {str(e)}")
                    # Fall through to alternative methods
            else:
                logger.info("AWS_EB_ENVIRONMENT_NAME not set, trying alternative restart methods")
        except ImportError:
            logger.info("boto3 not available, using alternative restart method")
        except Exception as e:
            logger.warning(f"Error attempting AWS restart: {str(e)}")
        
        # Alternative: For Gunicorn, we can trigger a graceful restart
        # This works by sending HUP signal to the master process
        try:
            import signal
            import sys
            
            # Get the parent process ID (Gunicorn master process)
            # In production, Gunicorn is the parent
            parent_pid = os.getppid()
            
            # Send HUP signal to trigger graceful restart (Gunicorn feature)
            # This reloads workers without dropping connections
            os.kill(parent_pid, signal.SIGHUP)
            
            logger.info("Server restart initiated via SIGHUP signal")
            return jsonify({
                "status": "success",
                "message": "Server restart initiated",
                "method": "Gunicorn graceful restart (SIGHUP)",
                "timestamp": datetime.now().isoformat()
            }), 200
            
        except (OSError, ProcessLookupError, AttributeError) as e:
            logger.warning(f"Signal-based restart not available: {str(e)}")
            # Fall through to final message
        
        # If all restart methods fail, return instructions
        return jsonify({
            "status": "info",
            "message": "Automatic restart not available",
            "instructions": "Please restart the server manually or configure AWS_EB_ENVIRONMENT_NAME for AWS restart",
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error in restart endpoint: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    Chat endpoint - Generate AI responses using OpenAI Assistant API.
    
    Request Body:
        - message (str, required): User's question
        - chart_data (dict, optional): Kundli/chart data for context
        - mode (str, optional): 'horary' for horary analysis, otherwise normal flow
    
    Assistant Selection:
        - Normal flow: Uses OPENAI_ASSISTANT_ID (default Assistant)
        - Horary flow: Uses OPENAI_ASSISTANT_ID_HORARY (horary-specific Assistant)
    
    Returns:
        JSON: AI response, timestamp, and assistant status
    """
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        chart_data = data.get('chart_data')  # Optional chart data for context
        # Mode can be sent as top-level or inside chart_data for frontend compatibility
        mode = (data.get('mode') or (chart_data.get('mode') if isinstance(chart_data, dict) else None) or '').strip().lower()

        if not user_message:
            return jsonify({
                "error": "Message is required"
            }), 400

        # Choose assistant id based on mode
        assistant_id_override = None
        if mode == 'horary':
            # Use dedicated Horary Assistant provided by the user
            assistant_id_override = os.getenv('OPENAI_ASSISTANT_ID_HORARY', 'asst_JkBy9ktoGmzRWMibVjFz09SO')

        # Get thread_id from request if provided (for conversation continuity)
        thread_id = data.get('thread_id')
        session_id = data.get('session_id')  # Optional session identifier
        
        # Generate AI response using Assistant API (with optional override and thread_id)
        result = astro_api.get_rag_response(user_message, chart_data, assistant_id_override=assistant_id_override, thread_id=thread_id)
        
        # Handle both old format (string) and new format (tuple with thread_id)
        if isinstance(result, tuple):
            ai_response, returned_thread_id = result
        else:
            ai_response = result
            returned_thread_id = None
        
        # Store thread_id in thread_store if session_id provided (with timestamp for cleanup)
        if session_id and returned_thread_id:
            thread_store[session_id] = {
                'thread_id': returned_thread_id,
                'last_used': datetime.now(),
                'created': thread_store.get(session_id, {}).get('created', datetime.now())
            }
            # Clean up old threads periodically (every 100 requests to avoid overhead)
            if len(thread_store) % 100 == 0:
                _cleanup_old_threads()
        
        response_data = {
            "response": ai_response,
            "timestamp": datetime.now().isoformat(),
            "user_message": user_message,
            "assistant_enabled": OPENAI_API_KEY is not None and (assistant_id_override or OPENAI_ASSISTANT_ID) is not None,
            "mode": mode or None
        }
        
        # Include thread_id in response for frontend to maintain conversation
        if returned_thread_id:
            response_data["thread_id"] = returned_thread_id
        
        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500

@app.route('/api/kundli', methods=['POST'])
def generate_kundli():
    """
    Kundli generation endpoint - Generate comprehensive astrological chart data.
    
    This endpoint:
    1. Parses birth data (flexible input formats)
    2. Geocodes place name to coordinates
    3. Calls all 14 ProKerala API endpoints in parallel:
       - Planet positions
       - Advanced Kundli
       - Bhava positions
       - Mangal Dosha
       - Auspicious Yoga
       - Sade Sati
       - Visual SVG chart
       - Kaal Sarp Dosha
       - Upagraha positions
       - General Yoga
       - Dasha periods
       - Planet relationships
       - Divisional planet positions
       - Chandrashtama periods
    
    Request Body:
        - name (str, required): Person's name
        - dob (str, required): Date of birth (YYYY-MM-DD or flexible format)
        - tob (str, required): Time of birth (HH:MM:SS or flexible format)
        - place (str, required): Place of birth (city name)
        - timezone (str, optional): Timezone (default: Asia/Kolkata)
    
    Returns:
        JSON: Complete chart data including all ProKerala API responses
    """
    try:
        logger.info("Received Kundli generation request")
        data = request.get_json()
        if not data:
            logger.warning("No data provided in request")
            return jsonify({"error": "No data provided"}), 400

        # Parse and normalize birth data using the flexible parser
        try:
            birth_data = parse_birth_data(data)
            logger.info(f"Parsed birth data for: {birth_data.get('name', 'Unknown')}")
        except ValueError as e:
            logger.error(f"Error parsing birth data: {e}")
            return jsonify({"error": str(e)}), 400

        # Get coordinates with timeout protection
        try:
            logger.info(f"Getting coordinates for place: {birth_data['place']}")
            latitude, longitude = astro_api.get_coordinates(birth_data['place'])
            logger.info(f"Coordinates: {latitude}, {longitude}")
        except Exception as geo_error:
            logger.error(f"Error getting coordinates: {geo_error}")
            return jsonify({
                "error": f"Failed to geocode place: {birth_data['place']}",
                "message": str(geo_error)
            }), 500

        # Calculate comprehensive chart data with error handling
        try:
            logger.info("Starting chart data calculation...")
            logger.info(f"Parameters: name={birth_data['name']}, dob={birth_data['dob_date']}, tob={birth_data['tob_time']}, place={birth_data['place']}")
            
            chart_data = astro_api.calculate_chart_data(
                birth_data['name'],
                birth_data['dob_date'],
                birth_data['tob_time'],
                birth_data['place'],
                latitude,
                longitude,
                birth_data['timezone']
            )
            
            if chart_data is None:
                logger.error("calculate_chart_data returned None - check ProKerala API credentials and connection")
                return jsonify({
                    "error": "Failed to generate Kundli chart data",
                    "message": "Chart calculation returned no data. Please check ProKerala API credentials."
                }), 500
                
            logger.info("Chart data calculation completed successfully")
        except Exception as calc_error:
            logger.error(f"Error calculating chart data: {calc_error}")
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Full traceback:\n{error_trace}")
            return jsonify({
                "error": "Failed to generate Kundli chart data",
                "message": str(calc_error),
                "details": error_trace.split('\n')[-5:] if len(error_trace) > 5 else error_trace
            }), 500

        if not chart_data:
            logger.error("Chart data is None or empty")
            return jsonify({
                "error": "Failed to generate Kundli. Please check your API credentials and try again."
            }), 500

        # Prepare response with size check
        try:
            # Check if chart_data is too large (prevent memory issues)
            chart_data_str = json.dumps(chart_data, default=str)
            chart_data_size = len(chart_data_str)
            logger.info(f"Chart data size: {chart_data_size} bytes")
            
            # If chart data is extremely large, truncate visual_chart SVG
            if chart_data_size > 5000000:  # 5MB limit
                logger.warning("Chart data is very large, truncating visual_chart SVG if present")
                if isinstance(chart_data, dict) and chart_data.get('visual_chart'):
                    # Keep only first 100KB of SVG
                    svg_content = chart_data.get('visual_chart', '')
                    if len(svg_content) > 100000:
                        chart_data['visual_chart'] = svg_content[:100000] + '... (truncated)'
                        logger.info("Truncated visual_chart SVG to prevent response size issues")
            
            response_data = {
                "success": True,
                "chart_data": chart_data,
                "parsed_data": {
                    "name": birth_data['name'],
                    "dob": birth_data['dob_date'].strftime('%Y-%m-%d'),
                    "tob": birth_data['tob_time'].strftime('%H:%M:%S'),
                    "place": birth_data['place'],
                    "timezone": birth_data['timezone'],
                    "coordinates": f"{latitude}, {longitude}"
                },
                "timestamp": datetime.now().isoformat()
            }
            
            # Test JSON serialization before sending
            try:
                test_json = json.dumps(response_data, default=str)
                logger.info(f"Response JSON size: {len(test_json)} bytes")
            except (TypeError, ValueError) as json_error:
                logger.error(f"JSON serialization error: {json_error}")
                # Try to fix serialization issues
                response_data = json.loads(json.dumps(response_data, default=str))
            
            logger.info("Kundli generation successful")
            return jsonify(response_data)
        except Exception as response_error:
            logger.error(f"Error preparing response: {response_error}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({
                "error": "Failed to prepare response",
                "message": str(response_error)
            }), 500

    except Exception as e:
        logger.error(f"Unexpected error in kundli endpoint: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            "error": "Failed to generate Kundli",
            "message": str(e)
        }), 500

@app.route('/api/test-prokerala', methods=['GET'])
def test_prokerala():
    """Test ProKerala API connection"""
    try:
        # Debug environment variables (do not leak secrets)
        debug_info = {
            "client_id_is_present": bool(PROKERALA_CLIENT_ID),
            "client_secret_is_present": bool(PROKERALA_CLIENT_SECRET)
        }

        access_token = astro_api.get_access_token()

        if not access_token:
            return jsonify({
                "error": "No access token available",
                "debug_info": debug_info
            }), 500

        # Test with ProKerala Chart endpoint
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            'ayanamsa': 5,
            'coordinates': '19.054999,72.840279',
            'datetime': '1990-03-15T10:30:00+05:30',
            'chart_type': 'rasi',
            'chart_style': 'north-indian',
            'format': 'svg'
        }

        # Use shared session via lazy getter
        response = astro_api._get_http().get('https://api.prokerala.com/v2/astrology/chart', headers=headers, params=params, timeout=15)

        content_type = response.headers.get('content-type', '')
        is_svg = 'svg' in content_type.lower() or response.text.strip().startswith('<svg')
        preview = response.text[:200]

        result = {
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "content_type": content_type,
            "is_svg": is_svg,
            "debug_info": debug_info
        }

        # Include a safe preview without JSON parsing errors
        if is_svg:
            result["response_preview"] = preview
        else:
            # Try JSON parse only if content-type hints JSON
            if 'application/json' in content_type.lower():
                try:
                    result["json"] = response.json()
                except Exception as e:
                    result["json_parse_error"] = str(e)
                    result["response_preview"] = preview
            else:
                result["response_preview"] = preview

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def parse_birth_data(data):
    """Parse and normalize birth data from various input formats"""
    try:
        # Extract and normalize name
        name = data.get('name', '').strip()
        if not name:
            name = data.get('full_name', '').strip()
        if not name:
            name = data.get('person_name', '').strip()

        # Extract and normalize date of birth
        dob_str = data.get('dob', '')
        if not dob_str:
            dob_str = data.get('date_of_birth', '')
        if not dob_str:
            dob_str = data.get('birth_date', '')
        if not dob_str:
            dob_str = data.get('birthday', '')

        # Extract and normalize time of birth
        tob_str = data.get('tob', '')
        if not tob_str:
            tob_str = data.get('time_of_birth', '')
        if not tob_str:
            tob_str = data.get('birth_time', '')
        if not tob_str:
            tob_str = data.get('time', '')

        # Extract and normalize place
        place = data.get('place', '')
        if not place:
            place = data.get('birth_place', '')
        if not place:
            place = data.get('location', '')
        if not place:
            place = data.get('city', '')

        # Extract timezone
        timezone_str = data.get('timezone', 'Asia/Kolkata')
        if not timezone_str:
            timezone_str = data.get('tz', 'Asia/Kolkata')

        # Validate required fields
        if not name:
            raise ValueError("Name is required")
        if not dob_str:
            raise ValueError("Date of birth is required")
        if not tob_str:
            raise ValueError("Time of birth is required")
        if not place:
            raise ValueError("Birth place is required")

        # Parse date with multiple format support
        dob_date = None
        date_formats = [
            '%Y-%m-%d',       # 2023-12-25
            '%d-%m-%Y',       # 25-12-2023
            '%m/%d/%Y',       # 12/25/2023
            '%d/%m/%Y',       # 25/12/2023
            '%Y/%m/%d',       # 2023/12/25
            '%d.%m.%Y',       # 25.12.2023
            '%m.%d.%Y',       # 12.25.2023
            '%d %m %Y',       # 25 12 2023
            '%B %d, %Y',      # December 25, 2023
            '%d %B %Y',       # 25 December 2023
        ]

        for fmt in date_formats:
            try:
                dob_date = datetime.strptime(dob_str.strip(), fmt).date()
                break
            except ValueError:
                continue

        if dob_date is None:
            raise ValueError(f"Unable to parse date: {dob_str}. Supported formats: YYYY-MM-DD, DD-MM-YYYY, MM/DD/YYYY, etc.")

        # Parse time with multiple format support
        tob_time = None
        time_formats = [
            '%H:%M:%S',       # 14:30:00
            '%H:%M',          # 14:30
            '%I:%M:%S %p',    # 02:30:00 PM
            '%I:%M %p',       # 02:30 PM
            '%I:%M:%S %p',    # 2:30:00 PM
            '%I:%M %p',       # 2:30 PM
        ]

        for fmt in time_formats:
            try:
                tob_time = datetime.strptime(tob_str.strip(), fmt).time()
                break
            except ValueError:
                continue

        if tob_time is None:
            raise ValueError(f"Unable to parse time: {tob_str}. Supported formats: HH:MM:SS, HH:MM, HH:MM AM/PM, etc.")

        # Normalize place name
        place = place.strip()

        return {
            'name': name,
            'dob_date': dob_date,
            'tob_time': tob_time,
            'place': place,
            'timezone': timezone_str
        }

    except Exception as e:
        logger.error(f"Error parsing birth data: {e}")
        raise ValueError(f"Data parsing error: {str(e)}")

@app.route('/api/chart', methods=['POST'])
def generate_chart():
    """Generate visual Kundli chart using ProKerala chart endpoint with flexible data input"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Parse and normalize birth data
        try:
            birth_data = parse_birth_data(data)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        # Get coordinates
        latitude, longitude = astro_api.get_coordinates(birth_data['place'])

        # Generate chart using ProKerala chart endpoint
        chart_data = astro_api.generate_chart_only(
            birth_data['name'],
            birth_data['dob_date'],
            birth_data['tob_time'],
            birth_data['place'],
            latitude,
            longitude,
            birth_data['timezone']
        )

        if chart_data:
            return jsonify({
                "success": True,
                "chart_data": chart_data,
                "parsed_data": {
                    "name": birth_data['name'],
                    "dob": birth_data['dob_date'].strftime('%Y-%m-%d'),
                    "tob": birth_data['tob_time'].strftime('%H:%M:%S'),
                    "place": birth_data['place'],
                    "timezone": birth_data['timezone'],
                    "coordinates": f"{latitude}, {longitude}"
                },
                "message": "Chart generated successfully"
            })
        else:
            return jsonify({"error": "Failed to generate chart"}), 500

    except Exception as e:
        logger.error(f"Error in chart generation: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/analyze', methods=['POST'])
def analyze_kundli():
    """Analyze Kundli data using OpenAI Assistant API.
    Select horary assistant when mode indicates horary usage.
    """
    try:
        data = request.get_json()
        chart_data = data.get('chart_data')
        question = data.get('question', 'Please analyze this Kundli')
        mode = (data.get('mode') or (chart_data.get('mode') if isinstance(chart_data, dict) else None) or '').strip().lower()

        if not chart_data:
            return jsonify({
                "error": "Chart data is required for analysis"
            }), 400

        # Choose assistant based on mode
        assistant_id_override = None
        if mode == 'horary':
            assistant_id_override = os.getenv('OPENAI_ASSISTANT_ID_HORARY', 'asst_JkBy9ktoGmzRWMibVjFz09SO')

        # Generate analysis using Assistant API
        analysis = astro_api.get_rag_response(question, chart_data, assistant_id_override=assistant_id_override)  # Method name kept for compatibility

        return jsonify({
            "analysis": analysis,
            "timestamp": datetime.now().isoformat(),
            "assistant_enabled": OPENAI_API_KEY is not None and (assistant_id_override or OPENAI_ASSISTANT_ID) is not None,
            "mode": mode or None
        })

    except Exception as e:
        logger.error(f"Error in analyze endpoint: {e}")
        return jsonify({
            "error": "Failed to analyze Kundli",
            "message": str(e)
        }), 500

@app.route('/api/form-submit', methods=['POST'])
def form_submit():
    """Append form submission to Google Sheet (optional)."""
    try:
        payload = request.get_json() or {}
        required = ['name', 'dob', 'tob', 'place', 'timezone']
        missing = [k for k in required if not str(payload.get(k, '')).strip()]
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

        # Try to append to Google Sheet (optional - not critical for core functionality)
        if append_form_submission is not None:
            try:
                logger.info(f"Attempting to save form data to Google Sheets for user: {payload.get('name', 'Unknown')}")
                # Ensure phone is a string (handle None, empty, or missing values)
                phone_value = str(payload.get('phone', '')).strip() if payload.get('phone') else ''
                
                append_form_submission(
                    spreadsheet_name=GOOGLE_SHEETS_SPREADSHEET_NAME,
                    worksheet_name=GOOGLE_SHEETS_WORKSHEET_NAME,
                    row_data=[
                        datetime.now().isoformat(),  # Column A: Timestamp
                        str(payload.get('name', '')).strip(),  # Column B: Name
                        phone_value,  # Column C: Phone Number (optional)
                        str(payload.get('dob', '')).strip(),  # Column D: Date of Birth
                        str(payload.get('tob', '')).strip(),  # Column E: Time of Birth
                        str(payload.get('place', '')).strip(),  # Column F: Place
                        str(payload.get('timezone', 'Asia/Kolkata')).strip(),  # Column G: Timezone
                        str(payload.get('mode', 'kundli')).strip(),  # Column H: Mode (kundli or horary)
                        '',  # Column I: Rating (empty for form-only rows)
                        ''  # Column J: Feedback Text (empty)
                    ]
                )
                logger.info("Form data successfully saved to Google Sheets")
            except Exception as sheets_error:
                logger.error(f"Google Sheets integration failed: {sheets_error}", exc_info=True)
                # Log full error details for debugging
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
            # Continue without Google Sheets - not critical
        else:
            logger.warning("Google Sheets integration not configured - skipping data storage. Check GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE environment variables.")

        return jsonify({"success": True, "message": "Form submitted successfully"})
    except HttpError as he:
        logger.error(f"Google Sheets API error: {he}")
        return jsonify({"error": "Google Sheets API error", "message": str(he)}), 500
    except Exception as e:
        logger.error(f"Error in form-submit endpoint: {e}")
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/api/sheets/diagnose', methods=['GET'])
def sheets_diagnose():
    """Check Google Sheets connectivity and env setup."""
    try:
        if diagnose_connection is None:
            return jsonify({"ok": False, "error": "Sheets module not available"}), 500
        result = diagnose_connection()
        # Attach non-sensitive env presence flags
        env_status = {
            "GOOGLE_CLIENT_ID": bool(os.getenv('GOOGLE_CLIENT_ID')),
            "GOOGLE_CLIENT_SECRET": bool(os.getenv('GOOGLE_CLIENT_SECRET')),
            "GOOGLE_REFRESH_TOKEN": bool(os.getenv('GOOGLE_REFRESH_TOKEN')),
            "GOOGLE_TOKEN_URI": bool(os.getenv('GOOGLE_TOKEN_URI')),
            "GOOGLE_SERVICE_ACCOUNT_JSON": bool(os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')),
            "GOOGLE_SERVICE_ACCOUNT_FILE": bool(os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')),
            "GOOGLE_SHEETS_SPREADSHEET_ID": bool(os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')),
            "GOOGLE_SHEETS_WORKSHEET_NAME": bool(os.getenv('GOOGLE_SHEETS_WORKSHEET_NAME')),
            "append_form_submission_available": append_form_submission is not None
        }
        # Include .env path diagnostics
        result.update({
            "env": env_status,
            "env_file_path": ENV_PATH,
            "env_file_exists": os.path.exists(ENV_PATH),
            "env_loaded": bool(ENV_LOADED),
            "cwd": os.getcwd()
        })
        return jsonify(result), (200 if result.get('ok') else 500)
    except Exception as e:
        logger.error(f"Error in sheets-diagnose endpoint: {e}", exc_info=True)
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/api/sheets/test-write', methods=['POST'])
def sheets_test_write():
    """Test writing to Google Sheets with sample data."""
    try:
        if append_form_submission is None:
            return jsonify({
                "ok": False,
                "error": "Google Sheets integration not configured. Check GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE environment variables."
            }), 500
        
        # Try to write a test row
        test_data = [
            datetime.now().isoformat(),  # Timestamp
            "Test User",  # Name
            "1234567890",  # Phone
            "1990-01-01",  # DOB
            "12:00:00",  # TOB
            "Test City",  # Place
            "Asia/Kolkata",  # Timezone
            "kundli",  # Mode
            "",  # Rating
            ""  # Feedback
        ]
        
        append_form_submission(
            spreadsheet_name=GOOGLE_SHEETS_SPREADSHEET_NAME,
            worksheet_name=GOOGLE_SHEETS_WORKSHEET_NAME,
            row_data=test_data
        )
        
        return jsonify({
            "ok": True,
            "message": "Test data successfully written to Google Sheets",
            "data": test_data
        })
    except Exception as e:
        logger.error(f"Test write failed: {e}", exc_info=True)
        import traceback
        return jsonify({
            "ok": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

@app.route('/api/sheets/test-form-submit', methods=['POST'])
def sheets_test_form_submit():
    """Test form submission with custom data - useful for debugging."""
    try:
        payload = request.get_json() or {}
        
        if append_form_submission is None:
            return jsonify({
                "ok": False,
                "error": "Google Sheets integration not configured. Check GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_SERVICE_ACCOUNT_FILE environment variables."
            }), 500
        
        # Use provided data or defaults for testing
        test_name = payload.get('name', 'Test User')
        test_phone = str(payload.get('phone', '')).strip() if payload.get('phone') else ''
        test_dob = payload.get('dob', '1990-01-01')
        test_tob = payload.get('tob', '12:00:00')
        test_place = payload.get('place', 'Test City')
        test_timezone = payload.get('timezone', 'Asia/Kolkata')
        test_mode = payload.get('mode', 'kundli')
        
        # Prepare row data exactly as form submission does
        row_data = [
            datetime.now().isoformat(),  # Column A: Timestamp
            str(test_name).strip(),  # Column B: Name
            test_phone,  # Column C: Phone Number (optional)
            str(test_dob).strip(),  # Column D: Date of Birth
            str(test_tob).strip(),  # Column E: Time of Birth
            str(test_place).strip(),  # Column F: Place
            str(test_timezone).strip(),  # Column G: Timezone
            str(test_mode).strip(),  # Column H: Mode (kundli or horary)
            '',  # Column I: Rating (empty for form-only rows)
            ''  # Column J: Feedback Text (empty)
        ]
        
        logger.info(f"Testing form submission with data: {row_data}")
        
        # Try to write to Google Sheets
        append_form_submission(
            spreadsheet_name=GOOGLE_SHEETS_SPREADSHEET_NAME,
            worksheet_name=GOOGLE_SHEETS_WORKSHEET_NAME,
            row_data=row_data
        )
        
        return jsonify({
            "ok": True,
            "message": "Test form data successfully written to Google Sheets!",
            "data_sent": {
                "name": test_name,
                "phone": test_phone,
                "dob": test_dob,
                "tob": test_tob,
                "place": test_place,
                "timezone": test_timezone,
                "mode": test_mode
            },
            "row_data": row_data,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Test form submit failed: {e}", exc_info=True)
        import traceback
        return jsonify({
            "ok": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }), 500

@app.route('/api/feedback-submit', methods=['POST'])
def feedback_submit():
    """
    Append feedback submission to Google Sheet.
    
    Stores user feedback (rating and comments) after chat session ends.
    This endpoint is called when the user submits feedback from the feedback modal.
    
    Request Body:
        - rating (int, required): User rating (1-5)
        - feedback (str, optional): Additional feedback text
        - timestamp (str, optional): ISO timestamp (auto-generated if not provided)
    
    Returns:
        JSON: Success or error message
    """
    try:
        payload = request.get_json() or {}
        
        # Validate required fields
        rating = payload.get('rating')
        if not rating or not isinstance(rating, int) or rating < 1 or rating > 5:
            return jsonify({"error": "Rating is required and must be between 1 and 5"}), 400
        
        feedback_text = payload.get('feedback', '').strip()
        timestamp = payload.get('timestamp', datetime.now().isoformat())
        
        # Try to append to Google Sheet (optional - not critical for core functionality)
        if append_form_submission is not None:
            try:
                # Use the same worksheet as form data
                append_form_submission(
                    spreadsheet_name=GOOGLE_SHEETS_SPREADSHEET_NAME,
                    worksheet_name=GOOGLE_SHEETS_WORKSHEET_NAME,
                    row_data=[
                        timestamp,  # Timestamp
                        '',  # Name (empty for feedback-only rows)
                        '',  # Date of Birth (empty)
                        '',  # Time of Birth (empty)
                        '',  # Place (empty)
                        '',  # Timezone (empty)
                        '',  # Mode (empty)
                        str(rating),  # Rating
                        feedback_text or 'N/A'  # Feedback Text
                    ]
                )
                logger.info(f"Feedback data successfully saved to Google Sheets (Rating: {rating})")
            except Exception as sheets_error:
                logger.warning(f"Google Sheets integration failed for feedback: {sheets_error}")
            # Continue without Google Sheets - not critical
        else:
            logger.info("Google Sheets integration not configured - skipping feedback storage")
        
        return jsonify({
            "success": True, 
            "message": "Feedback submitted successfully"
        })
    except HttpError as he:
        logger.error(f"Google Sheets API error: {he}")
        return jsonify({"error": "Google Sheets API error", "message": str(he)}), 500
    except Exception as e:
        logger.error(f"Error in feedback-submit endpoint: {e}")
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

if __name__ == '__main__':
    # Check configuration
    if not PROKERALA_CLIENT_ID or not PROKERALA_CLIENT_SECRET:
        logger.warning("ProKerala API credentials not found in environment variables")

    if not OPENAI_API_KEY:
        logger.warning("OpenAI API key not found - RAG features will be limited")

    logger.info("Starting Enhanced AstroBot Backend Server...")
    
    # PRODUCTION DEPLOYMENT
    # The app is deployed on AWS and uses Gunicorn (see Procfile)
    # Gunicorn is configured via Procfile for production deployment
    # For local development, run the app:
    # In production, Gunicorn is used via wsgi.py
    debug_mode = os.getenv('DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 5000))
    app.run(debug=debug_mode, host='0.0.0.0', port=port)