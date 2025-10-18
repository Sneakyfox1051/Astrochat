"""
AstroRemedis Backend API - Enhanced Astrology Chatbot

This is the main backend server for AstroRemedis, providing:
- AI-powered astrology consultations using OpenAI GPT-4
- Kundli chart generation via ProKerala API
- RAG (Retrieval Augmented Generation) with KP astrology rules
- Google Sheets integration for data storage
- Real-time chat with spiritual Pandit Ji persona

Key Features:
- Service Account authentication (no refresh tokens needed)
- Realistic and logical astrological predictions
- Spiritual, warm communication style
- Automatic chart generation and display
- Form data collection and storage

Author: AstroRemedis Development Team
Version: 2.0.0
Last Updated: 2024
"""

import os
import warnings
# Suppress ChromaDB telemetry warnings
os.environ['CHROMA_TELEMETRY'] = 'false'
# Suppress ONNX Runtime GPU warnings
warnings.filterwarnings('ignore', category=UserWarning, module='onnxruntime')

from flask import Flask, request, jsonify, send_from_directory
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

# LangChain imports - Optional for RAG functionality
try:
    from langchain_community.document_loaders import Docx2txtLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import Chroma
    # Use OpenAI embeddings directly instead of langchain-openai
    import openai
    RAG_AVAILABLE = True
except ImportError as e:
    logger.warning(f"LangChain dependencies not available. RAG functionality disabled. Error: {e}")
    RAG_AVAILABLE = False

class CustomOpenAIEmbeddings:
    """Custom OpenAI embeddings class to replace langchain-openai"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = openai.OpenAI(api_key=api_key)
    
    def embed_documents(self, texts):
        """Embed a list of documents"""
        try:
            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=texts
            )
            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            logger.error(f"Error embedding documents: {e}")
            return [[0.0] * 1536 for _ in texts]  # Fallback embeddings
    
    def embed_query(self, text):
        """Embed a single query"""
        try:
            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=[text]
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error embedding query: {e}")
            return [0.0] * 1536  # Fallback embedding

# Environment Configuration
# Load environment variables from backend/.env file
ENV_PATH = os.path.join(os.path.dirname(__file__), '.env')
# Force override to ensure backend/.env values are used even if shell has different vars
ENV_LOADED = load_dotenv(ENV_PATH, override=True)

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

# API Configuration
# ProKerala API credentials for Kundli chart generation
PROKERALA_CLIENT_ID = os.getenv('PROKERALA_CLIENT_ID')
PROKERALA_CLIENT_SECRET = os.getenv('PROKERALA_CLIENT_SECRET')

# OpenAI API key for AI-powered astrology consultations
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Google Sheets configuration (using Service Account authentication)
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_TOKEN_URI = os.getenv('GOOGLE_TOKEN_URI', 'https://oauth2.googleapis.com/token')
GOOGLE_REFRESH_TOKEN = os.getenv('GOOGLE_REFRESH_TOKEN')
GOOGLE_SHEETS_SPREADSHEET_NAME = os.getenv('GOOGLE_SHEETS_SPREADSHEET_NAME', 'AstroRemedis Data')
GOOGLE_SHEETS_WORKSHEET_NAME = os.getenv('GOOGLE_SHEETS_WORKSHEET_NAME', 'Sheet1')

try:
    from google_sheets import append_form_submission, diagnose_connection
    # Only enable if credentials are available
    if not os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON') and not os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE'):
        append_form_submission = None
        diagnose_connection = None
        logger.info("Google Sheets integration disabled - no credentials found")
except Exception as _e:
    append_form_submission = None
    diagnose_connection = None
    logger.warning(f"Google Sheets integration not available: {_e}")

# Constants
DOC_FILES = ["KP_RULE_1.docx", "KP_RULE_2.docx", "KP_RULE_3.docx"]
DEFAULT_LAT, DEFAULT_LON = 19.0760, 72.8777  # Mumbai Coordinates
DEFAULT_TZ = 'Asia/Kolkata'

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
            f"\n\nUpay {selected['category_name']}\n"
            f"1. {selected['free']}\n"
            f"2. {paid_one}\n"
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
    """Return True only when the user expresses a problem/pain, not generic inquiries.
    Ensures remedies are not added for neutral questions like "career ke bare mein bataiye".
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
    """Enhanced API class with RAG and advanced astrology features"""
    
    def __init__(self):
        self.access_token = None
        self.token_expiry = None
        self.vector_store = None
        if RAG_AVAILABLE:
            self._load_vector_store()
        else:
            logger.info("RAG system disabled - LangChain dependencies not available")
    
    def _load_vector_store(self):
        """Load and process Word documents for RAG"""
        if not RAG_AVAILABLE:
            logger.warning("Cannot load vector store - LangChain dependencies not available")
            return
            
        try:
            all_docs = []
            docs_path = os.path.join(os.path.dirname(__file__), '..', 'docs')
            
            for doc_file in DOC_FILES:
                file_path = os.path.join(docs_path, doc_file)
                if os.path.exists(file_path):
                    try:
                        loader = Docx2txtLoader(file_path)
                        all_docs.extend(loader.load())
                        logger.info(f"Loaded document: {doc_file}")
                    except Exception as e:
                        logger.error(f"Error loading {doc_file}: {e}")
                else:
                    logger.warning(f"Document file not found at {file_path}")

            if all_docs and OPENAI_API_KEY:
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
                texts = text_splitter.split_documents(all_docs)
                
                # Create embeddings using custom OpenAI embeddings
                embeddings = CustomOpenAIEmbeddings(OPENAI_API_KEY)
                
                # Create ChromaDB vector store (no Rust compilation required)
                self.vector_store = Chroma.from_documents(
                    documents=texts,
                    embedding=embeddings,
                    persist_directory="./chroma_db"
                )
                logger.info("Vector store loaded successfully with ChromaDB")
            else:
                logger.warning("No documents loaded or OpenAI API key missing")
                
        except Exception as e:
            logger.error(f"Error loading vector store: {e}")
            self.vector_store = None
    
    def get_access_token(self):
        """Get access token from ProKerala API with enhanced error handling"""
        logger.info(f"PROKERALA_CLIENT_ID set: {bool(PROKERALA_CLIENT_ID)}")
        logger.info(f"PROKERALA_CLIENT_SECRET set: {bool(PROKERALA_CLIENT_SECRET)}")
        
        if not PROKERALA_CLIENT_ID or not PROKERALA_CLIENT_SECRET:
            logger.error("ProKerala credentials not found in environment variables")
            return None
            
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token
            
        token_url = "https://api.prokerala.com/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": PROKERALA_CLIENT_ID,
            "client_secret": PROKERALA_CLIENT_SECRET,
        }

        try:
            response = requests.post(token_url, data=data)
            
            # Enhanced Authentication Error Check
            if response.status_code in [400, 401]:
                error_details = response.json().get('error_description', response.text)
                logger.error(f"Prokerala AUTH Failed (Status: {response.status_code}). Details: {error_details}")
                return None

            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data["access_token"]
            # Set expiry time (assuming 1 hour token validity)
            self.token_expiry = datetime.now().replace(microsecond=0, second=0, minute=0) + \
                              timedelta(hours=1)
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network Error during Prokerala Token request: {e}")
            return None
        except Exception as e:
            logger.error(f"Unknown Error during Prokerala Token request: {e}")
            return None

    def get_coordinates(self, place_name):
        """Get coordinates for a place name with fallback"""
        geolocator = Nominatim(user_agent="astrobot_app")
        try:
            location = geolocator.geocode(place_name, timeout=10)
            if location:
                return location.latitude, location.longitude
        except Exception as e:
            logger.warning(f"Geocoding failed for '{place_name}': {e}")
        return DEFAULT_LAT, DEFAULT_LON  # Fallback to Mumbai

    def _generate_mock_chart_data(self, name, dob_date, tob_time, pob_text, latitude, longitude, timezone_str):
        """Generate mock chart data for testing when API credentials are not available"""
        import random
        
        # Mock planetary positions
        planets_in_house = {}
        for house in range(1, 13):
            planets_in_house[house] = []
        
        # Assign some planets to random houses for demo
        planet_codes = ['Su', 'Mo', 'Ma', 'Me', 'Ju', 'Ve', 'Sa', 'Ra', 'Ke']
        assigned_planets = random.sample(planet_codes, 5)  # Assign 5 planets randomly
        
        for planet in assigned_planets:
            house = random.randint(1, 12)
            planets_in_house[house].append(planet)
        
        # Mock ascendant sign
        ascendant_signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 
                          'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
        ascendant_sign = random.randint(1, 12)
        ascendant_sign_name = ascendant_signs[ascendant_sign - 1]
        
        # Mock Mangal Dosha (30% chance of being present)
        mangal_dosha_present = random.random() < 0.3
        
        return {
            "name": name,
            "ascendant_sign": ascendant_sign,
            "ascendant_sign_name": ascendant_sign_name,
            "planets": planets_in_house,
            "mangal_dosha": {
                "is_present": mangal_dosha_present,
                "description": "Mangal Dosha present - may affect marriage timing" if mangal_dosha_present 
                              else "Mangal Dosha absent - favorable for marriage"
            },
            "birth_location": pob_text,
            "coordinates": {
                "latitude": latitude,
                "longitude": longitude
            },
            "timezone": timezone_str,
            "is_mock_data": True
        }

    def calculate_chart_data(self, name, dob_date, tob_time, pob_text, latitude, longitude, timezone_str):
        """Calculate comprehensive chart data including Mangal Dosha"""
        access_token = self.get_access_token()
        if not access_token:
            # Return mock data for testing when API credentials are not available
            logger.warning("ProKerala API credentials not available, returning mock data")
            return self._generate_mock_chart_data(name, dob_date, tob_time, pob_text, latitude, longitude, timezone_str)

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
            'sade_sati': {}
        }
        
        # Fetch Planet Positions
        try:
            planets_url = f"{base_url}/planet-position"
            planets_response = requests.get(planets_url, headers=headers, params=common_params)
            planets_response.raise_for_status()
            api_data['planet_positions'] = planets_response.json().get('data', {}).get('planet_position', [])
            logger.info("✅ Planet Positions fetched successfully")
        except Exception as e:
            logger.error(f"Error fetching Planet Positions: {e}")
            return None
            
        # Birth Details removed as per request
            
        # Fetch Kundli (Advanced)
        try:
            kundli_url = f"{base_url}/kundli/advanced"
            kundli_response = requests.get(kundli_url, headers=headers, params=common_params)
            kundli_response.raise_for_status()
            api_data['kundli'] = kundli_response.json().get('data', {})
            logger.info("✅ Kundli Advanced fetched successfully")
        except Exception as e:
            logger.error(f"Error fetching Kundli: {e}")
            api_data['kundli'] = {}
            
        # Use Kundli data for chart (JSON fallback)
        try:
            # The kundli data already contains chart information
            kundli_data = api_data.get('kundli', {})
            api_data['chart'] = {
                'kundli_data': kundli_data,
                'format': 'json',
                'chart_type': 'north-indian',
                'ayanamsa': 5,
                'astrology_system': 'KP'
            }
            logger.info("✅ Chart data extracted from Kundli successfully")
        except Exception as e:
            logger.error(f"Error processing Chart data: {e}")
            api_data['chart'] = {}
            
        # Fetch Bhava Positions (KP Houses)
        try:
            bhava_url = f"{base_url}/bhava-position"
            bhava_response = requests.get(bhava_url, headers=headers, params=common_params)
            bhava_response.raise_for_status()
            api_data['bhava_position'] = bhava_response.json().get('data', {}).get('bhava_position', [])
            logger.info("✅ Bhava Positions fetched successfully")
        except Exception as e:
            logger.error(f"Error fetching Bhava Positions: {e}")
            api_data['bhava_position'] = []

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
        bhava_map = {p.get('id'): p.get('bhava') for p in api_data.get('bhava_position', []) if p.get('id') is not None}
        if api_data['planet_positions']:
            for planet in api_data['planet_positions']:
                planet_id = planet.get('id')
                planet_name = planet.get('name')
                house_num = None
                if planet_id in bhava_map and isinstance(bhava_map[planet_id], int) and bhava_map[planet_id] > 0:
                    house_num = bhava_map[planet_id]
                elif ascendant_sign is not None:
                    sign_id = planet.get('rasi', {}).get('id')
                    if isinstance(sign_id, int):
                        house_num = (sign_id - ascendant_sign + 12) % 12 + 1
                
                if house_num is not None:
                    planet_code = planet_code_map.get(planet_name, (planet_name or '')[:2])
                    if house_num not in planets_in_house:
                        planets_in_house[house_num] = []
                    if planet_code and planet_code not in planets_in_house[house_num]:
                        planets_in_house[house_num].append(planet_code)
        # Final CHART_DATA Structure with comprehensive ProKerala data
        final_chart_data = {
            "name": name,
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
                "bhava_position": api_data.get('bhava_position', [])
            },
            
            # Chart Configuration
            "chart_config": {
                "ayanamsa": 5,
                "chart_style": "north-indian",
                "astrology_system": "KP"
            },
            
            # Legacy fields (best-effort) derived from Kundli Advanced if available
            "mangal_dosha": api_data.get('kundli', {}).get('mangal_dosha', {}),
            "dasha_periods": api_data.get('kundli', {}).get('dasha_periods', {}),
            "sade_sati": api_data.get('kundli', {}).get('sade_sati', {}),
            "yoga": api_data.get('kundli', {}).get('yoga_details', [])
        }
        
        return final_chart_data

    def generate_chart_only(self, name, dob_date, tob_time, pob_text, latitude, longitude, timezone_str):
        """Generate only the visual chart using ProKerala chart endpoint"""
        access_token = self.get_access_token()
        logger.info(f"Access token status: {'Available' if access_token else 'Not available'}")
        
        # Force use of real API for testing
        if not access_token:
            logger.warning("ProKerala API credentials not available, trying to get new token")
            # Try to get a fresh token
            access_token = self.get_access_token()
            if not access_token:
                logger.error("Still no access token available, returning mock chart")
                return self._generate_mock_chart(name, dob_date, tob_time, pob_text, latitude, longitude, timezone_str)

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
                chart_response = requests.get(chart_url, headers=headers, params=chart_params)
                
                logger.info(f"Chart Response Status: {chart_response.status_code}")
                logger.info(f"Chart Response Content-Type: {chart_response.headers.get('content-type', '')}")
                
                if chart_response.status_code != 200:
                    logger.error(f"Chart API Error: {chart_response.text}")
                    return self._generate_mock_chart(name, dob_date, tob_time, pob_text, latitude, longitude, timezone_str)
                
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
                return self._generate_mock_chart(name, dob_date, tob_time, pob_text, latitude, longitude, timezone_str)
                
        except Exception as e:
            logger.error(f"Timezone or Date/Time Error: {e}")
            return self._generate_mock_chart(name, dob_date, tob_time, pob_text, latitude, longitude, timezone_str)

    def _generate_mock_chart(self, name, dob_date, tob_time, pob_text, latitude, longitude, timezone_str):
        """Generate mock chart for testing"""
        return {
            'svg_content': f'''<svg width="400" height="400" xmlns="http://www.w3.org/2000/svg">
                <circle cx="200" cy="200" r="180" fill="none" stroke="#333" stroke-width="2"/>
                <text x="200" y="50" text-anchor="middle" font-size="16" font-weight="bold">🌟 {name}'s Kundli Chart</text>
                <text x="200" y="80" text-anchor="middle" font-size="12">KP Astrology (Ayanamsa 5)</text>
                <text x="200" y="100" text-anchor="middle" font-size="12">North Indian Style</text>
                <text x="200" y="130" text-anchor="middle" font-size="10">Birth: {dob_date} {tob_time}</text>
                <text x="200" y="150" text-anchor="middle" font-size="10">Place: {pob_text}</text>
                <text x="200" y="350" text-anchor="middle" font-size="12" fill="#666">Mock Chart - Real chart will be generated with ProKerala API</text>
            </svg>''',
            'format': 'svg',
            'chart_type': 'north-indian',
            'ayanamsa': 5,
            'astrology_system': 'KP',
            'is_mock': True
        }

    def _get_basic_ai_response(self, question, chart_data):
        """Basic AI response without RAG when LangChain is not available"""
        if not OPENAI_API_KEY:
            return "Sorry, main abhi online nahi hun. Kripya thodi der baad try karein."
        
        try:
            # Simple prompt without RAG context
            system_prompt = f"""
            Aap AstroRemedis ke Digital Pandit Ji hain — ek experienced astrologer jo KP (Krishnamurti Paddhati) astrology mein expert hain.
            
            Aapka style:
            - Warm, spiritual, aur caring
            - Practical remedies suggest karte hain
            - Hindi mein respond karte hain
            - Astrological insights provide karte hain
            
            User ka prashna: "{question}"
            
            Please provide a helpful astrological response in Hindi.
            """
            
            response = openai.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error in basic AI response: {e}")
            return "Sorry, main abhi online nahi hun. Kripya thodi der baad try karein."
    
    def get_rag_response(self, question, chart_data, conversation_history=None):
        """Get AI response using RAG with chart data and KP rules and append remedies."""
        if not RAG_AVAILABLE:
            # Fallback to basic OpenAI response without RAG
            return self._get_basic_ai_response(question, chart_data)
            
        if self.vector_store is None or not OPENAI_API_KEY:
            return "The knowledge base is not loaded or OpenAI API key is missing. Please check your configuration."
            
        try:
            # Ensure variable exists in all code paths
            earliest_marriage_year = 0
            retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})
            relevant_docs = retriever.invoke(question)
            # Concise RAG context (cap total size to avoid token limits)
            raw_docs = "\n\n".join([doc.page_content for doc in relevant_docs])
            context_from_docs = raw_docs[:2000]  # cap to ~2k chars

            # Age calculation for realistic predictions
            dob_date = chart_data.get('dob_date')
            if isinstance(dob_date, str):
                try:
                    dob_date = datetime.strptime(dob_date, '%Y-%m-%d').date()
                except:
                    dob_date = datetime(2000, 1, 1).date()
            elif not dob_date:
                dob_date = datetime(2000, 1, 1).date()
            
            current_year = datetime.now().year
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
            **CURRENT YEAR: 2025** - All predictions must be for 2025 onwards.
            Question Type: {response_style}.
            Minimum realistic age for this event is {minimum_age_threshold} years. 
            Prediction year MUST be >= {earliest_realistic_year} AND >= 2025.
            If the Dasha data shows a favorable time before {earliest_realistic_year} or before 2025, IGNORE it and find the next favorable timing after {earliest_realistic_year} and 2025.
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
                    birth_details = prokerala.get('birth_details') or {}
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

            compact_chart = build_compact_chart(chart_data or {})
            chart_context = json.dumps(compact_chart, ensure_ascii=False)
            if len(chart_context) > 3000:
                chart_context = chart_context[:3000]

            # Context-aware follow-up questions based on the user's question
            follow_up_questions = {
                "career": [
                    "Aapka current job role kya hai aur kya aap usse satisfied hain?",
                    "Kya aap job change ya promotion ke baare mein soch rahe hain?",
                    "Aapke career goals kya hain jo aap achieve karna chahte hain?",
                    "Kya aap koi naya business start karna chahte hain?",
                    "Aapke field mein kya challenges aa rahe hain?",
                    "Kya aapko lagta hai ki aapka talent properly utilize ho raha hai?",
                    "Aapke dream job kya hai aur uske liye kya karna hoga?",
                    "Kya aapko lagta hai ki aapka current role aapke potential ke saath match karta hai?",
                    "Aapke industry mein future prospects kya lagte hain?",
                    "Kya aapko lagta hai ki aapka boss aapko appreciate karta hai?",
                    "Aapke colleagues ke saath relationship kaise hai?",
                    "Kya aapko lagta hai ki aapka work-life balance theek hai?",
                    "Aapke field mein kya skills develop karni chahiye?",
                    "Kya aapko lagta hai ki aapka current company mein growth hai?",
                    "Aapke career mein kya biggest achievement hai ab tak?"
                ],
                "relationship": [
                    "Kya aapke rishte ki baat chal rahi hai kya?",
                    "Aapki current relationship status kya hai?",
                    "Kya aap marriage ke liye ready hain ya koi specific concerns hain?",
                    "Aapke family mein koi pressure hai marriage ke liye?",
                    "Aapke partner ke saath kya issues hain jo solve karni hain?",
                    "Kya aapko lagta hai ki aapka partner aapko samajhta hai?",
                    "Aapke relationship mein trust ki situation kaise hai?",
                    "Kya aapko lagta hai ki aapka partner aapke dreams ko support karta hai?",
                    "Aapke relationship mein communication kaise hai?",
                    "Kya aapko lagta hai ki aapka partner aapke family ko pasand karta hai?",
                    "Aapke relationship mein kya biggest challenge hai?",
                    "Kya aapko lagta hai ki aapka partner aapke career ko support karta hai?",
                    "Aapke relationship mein romance kaise hai?",
                    "Kya aapko lagta hai ki aapka partner aapke values ke saath match karta hai?",
                    "Aapke relationship mein future planning kaise hai?"
                ],
                "health": [
                    "Aapko koi specific health issues hain jo aapko pareshan kar rahe hain?",
                    "Kya aap regular exercise aur healthy diet follow karte hain?",
                    "Aapke family mein koi hereditary health problems hain?",
                    "Kya aap stress ya anxiety se deal kar rahe hain?",
                    "Aapki sleep pattern kaise hai?",
                    "Kya aapko lagta hai ki aapka energy level theek hai?",
                    "Aapke daily routine mein kya health activities hain?",
                    "Kya aapko lagta hai ki aapka mental health theek hai?",
                    "Aapke diet mein kya improvements kar sakte hain?",
                    "Kya aapko lagta hai ki aapka work stress aapke health ko affect kar raha hai?",
                    "Aapke family mein koi health history hai jo aapko concern karti hai?",
                    "Kya aapko lagta hai ki aapka lifestyle healthy hai?",
                    "Aapke health goals kya hain jo aap achieve karna chahte hain?",
                    "Kya aapko lagta hai ki aapka environment healthy hai?",
                    "Aapke health mein kya biggest concern hai?"
                ],
                "general": [
                    "Aapke man mein aur kya sawaal hai jiska jawab aap chahte hain?",
                    "Kya aap koi specific problem face kar rahe hain jo solve karna chahte hain?",
                    "Aapke life mein koi major changes aane wale hain?",
                    "Kya aap koi important decision lene wale hain?",
                    "Aapke life mein kya biggest challenge hai abhi?",
                    "Kya aapko lagta hai ki aapka life mein balance hai?",
                    "Aapke family ke saath relationship kaise hai?",
                    "Kya aapko lagta hai ki aapka life mein purpose hai?",
                    "Aapke friends aur social circle kaise hai?",
                    "Kya aapko lagta hai ki aapka life mein happiness hai?",
                    "Aapke life mein kya biggest fear hai?",
                    "Kya aapko lagta hai ki aapka life mein peace hai?",
                    "Aapke life mein kya biggest dream hai?",
                    "Kya aapko lagta hai ki aapka life mein growth hai?",
                    "Aapke life mein kya biggest regret hai?"
                ]
            }
            
            # Select appropriate follow-up question based on response style
            follow_up_instruction = ""
            if response_style in ["relationship_advice", "career_guidance", "health_guidance"]:
                import random
                import time
                
                # Map response styles to follow-up categories
                follow_up_category = {
                    "relationship_advice": "relationship",
                    "career_guidance": "career", 
                    "health_guidance": "health"
                }.get(response_style, "general")
                
                # Use current time to ensure different questions each time
                random.seed(int(time.time()) % 1000)
                follow_up_question = random.choice(follow_up_questions[follow_up_category])
                
                # Add variety in question introduction
                question_intros = [
                    "At the very end of your response, gently ask the user this question to continue the flow:",
                    "End your response by asking this follow-up question naturally:",
                    "Conclude your response with this question to keep the conversation flowing:",
                    "Finish your response by asking this question to engage the user further:",
                    "End with this question to continue the meaningful conversation:"
                ]
                
                intro = random.choice(question_intros)
                follow_up_instruction = f"{intro} '{follow_up_question}'"

            # Build remedies section only if the question implies a problem/pain
            remedies_section = generate_remedies(question, chart_data, compact=True) if should_append_remedies(question) else ""

            safe_earliest_marriage_year = earliest_marriage_year or (birth_year + min_ages["relationship_advice"])
            logger.info(f"[AI] response_style={response_style}, earliest_realistic_year={earliest_realistic_year}, earliest_marriage_year={safe_earliest_marriage_year}")

            system_prompt = f"""
            You are AstroBot, an experienced, calm, wise, and compassionate KP Jyotishacharya (Digital Pandit Ji). 
            Your persona MUST match this EXACT structure and tone (using Hinglish and appropriate greetings):
            1. Start with a spiritual Hindi/Hinglish acknowledgment (e.g., "Aapka sawaal uttam hai, {chart_data.get('name', 'User')} ji...").
            2. State the prediction in a clear, narrative style using Hinglish with SPECIFIC future timeframes (2025 onwards).
            3. If the prediction relates to children, use the '🔮 Santan Yog Prediction' heading and explain the timing.
            4. Conclude with a spiritual blessing ("Shri Sitaram...") and the follow-up question.

            **CRITICAL & NON-NEGOTIABLE RULES (Tone & Style):**
            1. **Greeting/Acknowledge:** Use a personalized and spiritual opening.
            2. **Length/Focus:** Be **EXTREMELY SUCCINCT** and **LASER-FOCUSED**. Limit the core prediction/explanation to **3-5 sentences MAXIMUM**.
            3. **Graha Explanation: ⛔ STRICTLY FORBIDDEN (ABSOLUTE ZERO TOLERANCE) ⛔:** **NEVER** mention any planet (Graha), house, sign, dasha, sub-lord, yog, sthiti, ya koi bhi astrological terminology (jyotish shabda) in the final response. Use this information only internally to form the prediction.
            4. **Formatting:** When predicting children, use the heading '🔮 Santan Yog Prediction' exactly as shown.
            5. **SINGLE FOLLOW-UP ONLY:** {follow_up_instruction}
            6. **NO GENERIC QUESTIONS:** Avoid asking generic questions like "What is your next question?" or "On which topic do you want to focus next?" Use the specific follow-up question provided.
            7. **REMEDY FORMAT:** If remedies are provided, include them in the SAME response as plain text (no markdown formatting, no **Upay:** headers, no special formatting).

            **CRITICAL ACCURACY & LOGIC RULES (Prediction Accuracy and Realism):**
            6. **Data-Driven:** Base your answer strictly on the provided CHART DATA and KP ASTROLOGY KNOWLEDGE.
            7. **CURRENT YEAR AWARENESS:** We are currently in 2025. ALL predictions must be for FUTURE years (2025 onwards). NEVER mention past years like 2023-2025.
            8. **AGE/LOGIC OVERRIDE (NON-NEGOTIABLE):** For any prediction, the **Prediction Year MUST be GREATER THAN or EQUAL TO** the **Earliest Realistic Year** ({earliest_realistic_year}).
            9. **CHRONOLOGY CHECK (CHILDREN ONLY):** If the question is about **Children/Santan**, you **MUST** ensure the prediction year is **AT LEAST 1 YEAR GREATER** than the earliest realistic marriage year ({safe_earliest_marriage_year}).
            10. **Dasha Priority (Timing Source):** The timing for prediction MUST be sourced from the Dasha periods, ensuring all chronological and logical rules are satisfied.
            11. **Time Reference:** ALWAYS use specific FUTURE years/timeframes (e.g., 'mid-2026', '2027-2028', 'late 2025') derived from the Dasha data, ensuring they are **logically sound and future-oriented**.
            12. **REMEDY INSTRUCTION (NON-NEGOTIABLE):** If remedies are provided, include them in your main response as plain text (no markdown, no special formatting) before the spiritual blessing and follow-up question.

            **User's Question:** "{question}"

            **INTERNAL REFERENCE DATA (Analyze and Apply Rules):**
            {chart_context}
            
            **KP ASTROLOGY KNOWLEDGE (Internal Reference Only):**
            {context_from_docs}
            
            {age_logic_context}

            Provide the response now, following ALL the above rules.
            {('MANDATORY: You MUST include these EXACT remedies in your response as plain text (copy them exactly): ' + remedies_section) if remedies_section else ''}
                        """
            
            try:
                response = openai.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[{"role": "user", "content": system_prompt}],
                    temperature=0.9,
                    max_tokens=800
                )
                return response.choices[0].message.content
            except Exception as primary_error:
                try:
                    short_prompt = system_prompt
                    if len(short_prompt) > 6000:
                        short_prompt = short_prompt[:6000]
                    response = openai.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": short_prompt}]
                    )
                    return response.choices[0].message.content
                except Exception as fallback_error:
                    logger.error(f"OpenAI error primary: {primary_error}; fallback: {fallback_error}")
                    return "Sorry, I encountered a temporary AI capacity issue. Please ask again in a few seconds."
            
        except Exception as e:
            logger.error(f"Error in RAG response: {e}")
            return f"Sorry, I encountered an error with the AI model: {e}"

    def generate_ai_response(self, user_message, chart_data=None):
        """Generate AI response - use RAG if chart data available, otherwise basic response"""
        if chart_data and self.vector_store and OPENAI_API_KEY:
            return self.get_rag_response(user_message, chart_data)
        else:
            # Fallback to basic astrology responses
            return self._get_basic_response(user_message)
    
    def _get_basic_response(self, user_message):
        """Basic astrology response when RAG is not available"""
        user_message_lower = user_message.lower()
        
        if any(word in user_message_lower for word in ['hello', 'hi', 'namaste', 'namaskar', 'pranam']):
            return "Namaste! 🙏 Main Pandit ji hun. Aapka swagat hai AstroRemedis mein!"
        
        if any(word in user_message_lower for word in ['kundli', 'horoscope', 'chart', 'birth chart']):
            return "Aapka Kundli analysis karne ke liye, main aapke birth details chahiye. Kripya apna date of birth, time of birth aur place of birth batayiye."
        
        astrology_keywords = {
            'marriage': 'Marriage ke liye main aapke 7th house aur Venus position check karunga. Birth details chahiye.',
            'career': 'Career guidance ke liye main aapke 10th house aur Saturn position analyze karunga.',
            'health': 'Health ke liye main aapke 6th house aur Mars position check karunga.',
            'finance': 'Finance aur wealth ke liye main aapke 2nd house aur Jupiter position analyze karunga.',
            'education': 'Education ke liye main aapke 5th house aur Mercury position check karunga.',
            'travel': 'Travel ke liye main aapke 9th house aur Jupiter position analyze karunga.',
            'property': 'Property ke liye main aapke 4th house aur Moon position check karunga.',
            'children': 'Children ke liye main aapke 5th house aur Jupiter position analyze karunga.'
        }
        
        for keyword, response in astrology_keywords.items():
            if keyword in user_message_lower:
                return response
        
        return "Namaste! 🙏 Main aapki astrology-related queries solve kar sakta hun. Aap kya jaanna chahte hain? Kundli, horoscope, marriage, career, health, ya koi aur topic?"

# Initialize enhanced API instance
astro_api = EnhancedAstroBotAPI()

@app.route('/')
def home():
    """Home endpoint"""
    return jsonify({
        "message": "Enhanced AstroBot API is running!",
        "version": "2.0.0",
        "features": [
            "RAG (Retrieval Augmented Generation)",
            "LangChain Integration",
            "Mangal Dosha Calculation",
            "Advanced AI Responses",
            "Timezone Support"
        ],
        "endpoints": {
            "chat": "/api/chat",
            "kundli": "/api/kundli",
            "analyze": "/api/analyze",
            "health": "/api/health"
        }
    })

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "features": {
            "rag_enabled": RAG_AVAILABLE and astro_api.vector_store is not None,
            "openai_enabled": OPENAI_API_KEY is not None,
            "prokerala_enabled": PROKERALA_CLIENT_ID is not None
        }
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    """Enhanced chat endpoint with RAG support"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        chart_data = data.get('chart_data')  # Optional chart data for context
        
        if not user_message:
            return jsonify({
                "error": "Message is required"
            }), 400
        
        # Generate AI response using RAG if chart data available
        ai_response = astro_api.generate_ai_response(user_message, chart_data)
        
        return jsonify({
            "response": ai_response,
            "timestamp": datetime.now().isoformat(),
            "user_message": user_message,
            "rag_enabled": astro_api.vector_store is not None
        })
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500

@app.route('/api/kundli', methods=['POST'])
def generate_kundli():
    """Enhanced Kundli generation with flexible data input"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # Parse and normalize birth data using the flexible parser
        try:
            birth_data = parse_birth_data(data)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        
        # Get coordinates
        latitude, longitude = astro_api.get_coordinates(birth_data['place'])
        
        # Calculate comprehensive chart data
        chart_data = astro_api.calculate_chart_data(
            birth_data['name'],
            birth_data['dob_date'],
            birth_data['tob_time'],
            birth_data['place'],
            latitude,
            longitude,
            birth_data['timezone']
        )
        
        if not chart_data:
            return jsonify({
                "error": "Failed to generate Kundli. Please check your API credentials and try again."
            }), 500
        
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
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in kundli endpoint: {e}")
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
        
        response = requests.get('https://api.prokerala.com/v2/astrology/chart', headers=headers, params=params)

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
            '%Y-%m-%d',      # 2023-12-25
            '%d-%m-%Y',      # 25-12-2023
            '%m/%d/%Y',      # 12/25/2023
            '%d/%m/%Y',      # 25/12/2023
            '%Y/%m/%d',      # 2023/12/25
            '%d.%m.%Y',      # 25.12.2023
            '%m.%d.%Y',      # 12.25.2023
            '%d %m %Y',      # 25 12 2023
            '%B %d, %Y',     # December 25, 2023
            '%d %B %Y',      # 25 December 2023
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
            '%H:%M:%S',      # 14:30:00
            '%H:%M',         # 14:30
            '%I:%M:%S %p',   # 02:30:00 PM
            '%I:%M %p',      # 02:30 PM
            '%I:%M:%S %p',   # 2:30:00 PM
            '%I:%M %p',      # 2:30 PM
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
    """Analyze Kundli data using RAG"""
    try:
        data = request.get_json()
        chart_data = data.get('chart_data')
        question = data.get('question', 'Please analyze this Kundli')
        
        if not chart_data:
            return jsonify({
                "error": "Chart data is required for analysis"
            }), 400
        
        # Generate analysis using RAG
        analysis = astro_api.get_rag_response(question, chart_data)
        
        return jsonify({
            "analysis": analysis,
            "timestamp": datetime.now().isoformat(),
            "rag_enabled": astro_api.vector_store is not None
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
                append_form_submission(
                    spreadsheet_name=GOOGLE_SHEETS_SPREADSHEET_NAME,
                    worksheet_name=GOOGLE_SHEETS_WORKSHEET_NAME,
                    row_data=[
                        datetime.now().isoformat(),
                        payload['name'],
                        payload['dob'],
                        payload['tob'],
                        payload['place'],
                        payload.get('timezone', 'Asia/Kolkata')
                    ]
                )
                logger.info("Form data successfully saved to Google Sheets")
            except Exception as sheets_error:
                logger.warning(f"Google Sheets integration failed: {sheets_error}")
                # Continue without Google Sheets - not critical
        else:
            logger.info("Google Sheets integration not configured - skipping data storage")

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
            "GOOGLE_SHEETS_SPREADSHEET_ID": bool(os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')),
            "GOOGLE_SHEETS_WORKSHEET_NAME": bool(os.getenv('GOOGLE_SHEETS_WORKSHEET_NAME'))
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
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == '__main__':
    # Check configuration
    if not PROKERALA_CLIENT_ID or not PROKERALA_CLIENT_SECRET:
        logger.warning("ProKerala API credentials not found in environment variables")
    
    if not OPENAI_API_KEY:
        logger.warning("OpenAI API key not found - RAG features will be limited")
    
    logger.info("Starting Enhanced AstroBot Backend Server...")
    app.run(debug=True, host='0.0.0.0', port=5000)
