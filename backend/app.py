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
Version: 2.0.0 (Final Logic Integrated)
Last Updated: 2025
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
import random

# Configure logging early (needed for early warnings)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Output sanitizer to enforce client feedback: remove code-like junk and keep it concise
def sanitize_ai_text(text: str) -> str:
    try:
        if not text:
            return ""
        cleaned = str(text)
        # Remove inline code or script-ish fragments
        patterns = [
            r"\$\([^\)]*\)",            # jQuery-like $(...)
            r"</?script[^>]*>",            # <script> tags
            r"[{}();<>]{2,}",              # sequences of code punctuation
            r"#[A-Za-z0-9_-]+\([^)]*\)",  # selector-like foo(#id)
        ]
        import re
        for pat in patterns:
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)
        # Normalize newlines and bullets while preserving line breaks
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
        # Unify common bullet characters to '- '
        cleaned = re.sub(r"[•\u2022\u2023\u2043\u2219\u25E6\u204C\u204D\u2219]+\s*", "- ", cleaned)
        # Ensure each '- ' bullet starts on a new line
        cleaned = re.sub(r"(?m)(?<!^)(?:\s)+- ", "\n- ", cleaned)
        # Collapse excessive spaces and tabs but keep newlines
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        # Limit multiple blank lines to a single blank line
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        # Hard length cap for safety
        if len(cleaned) > 900:
            cleaned = cleaned[:900]
            last_period = cleaned.rfind('.')
            if last_period > 700:
                cleaned = cleaned[:last_period + 1]
        return cleaned
    except Exception:
        return text

# Identity consistency enforcer to keep Lagna/Chandra Rashi/Mahadasha stable and avoid repetition
def enforce_identity_consistency(text: str, profile: dict = None, suppress_identities: bool = False) -> str:
    """
    - If profile contains exact `lagna`, `chandra_rashi`, `mahadasha`, normalize any mentions to these exact values.
    - If suppress_identities is True, remove repeated Lagna/Rashi/Dasha lines from subsequent replies.
    - Scrub generic remedies (e.g., "Saturday tel daan") unless they match the observed planet context.
    """
    if not text:
        return text
    try:
        import re
        t = text.replace("\r\n", "\n").replace("\r", "\n")

        if profile:
            def sub_identity(label, value):
                if not value:
                    return
                if label == 'lagna':
                    patterns = [
                        r"(?im)^(?:lagna|ascendant)\s*[:\-]\s*.+$",
                        r"(?i)(lagna|ascendant)\b[^\n]*"
                    ]
                    replacement = f"Lagna {value}"
                elif label == 'chandra_rashi':
                    patterns = [
                        r"(?im)^(?:chandra\s*rashi|moon\s*sign|moonsign)\s*[:\-]\s*.+$",
                        r"(?i)(chandra\s*rashi|moon\s*sign|moonsign)\b[^\n]*"
                    ]
                    replacement = f"Chandra Rashi {value}"
                elif label == 'mahadasha':
                    patterns = [
                        r"(?im)^(?:maha\s*dasha|mahadasha|current\s*dasha)\s*[:\-]\s*.+$",
                        r"(?i)(maha\s*dasha|mahadasha|current\s*dasha)\b[^\n]*"
                    ]
                    replacement = f"Mahadasha {value}"
                else:
                    return
                for pat in patterns:
                    t = re.sub(pat, replacement, t)

            sub_identity('lagna', profile.get('lagna'))
            sub_identity('chandra_rashi', profile.get('chandra_rashi'))
            sub_identity('mahadasha', profile.get('mahadasha'))

        # Remove redundant phrasing like "Moonsign" duplicates
        t = re.sub(r"(?i)\bmoonsign\b", "Moon sign", t)

        # Scrub generic remedies when planet mismatch is likely
        # If profile has planet data but text includes generic "Saturday tel daan" – remove that specific line
        if profile and profile.get('mahadasha'):
            # If mahadasha is NOT Shani but text has "Saturday tel daan", remove it
            maha_val = profile.get('mahadasha', '').lower()
            if 'shani' not in maha_val and 'shaniv' not in maha_val:
                t = re.sub(r"(?i)(saturday ko|shanivar ko).*?tel daan.*?\n", "", t, flags=re.MULTILINE)

        if suppress_identities:
            lines = t.split("\n")
            kept = []
            for line in lines:
                if re.search(r"(?i)\b(lagna|ascendant|chandra\s*rashi|moon\s*sign|maha\s*dasha|mahadasha)\b", line):
                    continue
                kept.append(line)
            t = "\n".join(kept)

        return t
    except Exception:
        return text

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
# Enable CORS for frontend communication (allow Netlify and local dev)
CORS(
    app,
    resources={r"/api/*": {"origins": [
        "*",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://gilded-baklava-db352f.netlify.app"
    ]}},
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    supports_credentials=False
)

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
DOC_FILES = ["KP_RULE_1.docx", "KP_RULE_2.docx", "KP_RULE_3.docx", "Laal KItab.docx"]
DEFAULT_LAT, DEFAULT_LON = 19.0760, 72.8777  # Mumbai Coordinates
DEFAULT_TZ = 'Asia/Kolkata'

# Lal Kitab Environment Detection Rules
LAL_KITAB_ENVIRONMENT_RULES = {
    'Shani': {
        'triggers': ['hospital', 'loha', 'old area', 'iron', 'metal', 'construction'],
        'observation': "Aapke grahon se lagta hai aapke ghar ke paas hospital ya darji ki dukaan hai.",
        'remedy': "Saturday ko tel daan karen, Shani prasann rahenge."
    },
    'Mangal': {
        'triggers': ['tailoring', 'mechanic', 'iron shop', 'garage', 'workshop', 'cutting'],
        'observation': "Aapke grahon se lagta hai aapke ghar ke paas tailoring ya mechanic ki dukaan hai.",
        'remedy': "Mangalwar ko hanuman chalisa ka path karein."
    },
    'Rahu': {
        'triggers': ['drain', 'mobile tower', 'nala', 'sewer', 'telecom', 'antenna'],
        'observation': "Aapke grahon se lagta hai aapke ghar ke paas drain ya mobile tower hai.",
        'remedy': "Rahu ke liye coconut daan karein."
    },
    'Guru': {
        'triggers': ['school', 'mandir', 'temple', 'college', 'education', 'religious'],
        'observation': "Aapke grahon se lagta hai aapke ghar ke paas school ya mandir hai.",
        'remedy': "Guruwar ko gau mata ko hara chara khilayein."
    },
    'Shukra': {
        'triggers': ['beauty parlour', 'jewellery', 'cosmetics', 'fashion', 'salon'],
        'observation': "Aapke grahon se lagta hai aapke ghar ke paas beauty parlour ya jewellery shop hai.",
        'remedy': "Shukrawar ko peepal ke ped ko doodh arpit karein."
    },
    'Budh': {
        'triggers': ['stationery', 'printing', 'book', 'paper', 'office supplies'],
        'observation': "Aapke grahon se lagta hai aapke ghar ke paas stationery ya printing shop hai.",
        'remedy': "Budhwar ko green moong daal daan karein."
    },
    'Surya': {
        'triggers': ['government office', 'court', 'police', 'administration', 'official'],
        'observation': "Aapke grahon se lagta hai aapke ghar ke paas government office ya court hai.",
        'remedy': "Ravivar ko copper ke bartan se Surya Dev ko jal arpit karein."
    },
    'Chandra': {
        'triggers': ['paani', 'dairy', 'water', 'milk', 'pond', 'lake'],
        'observation': "Aapke grahon se lagta hai aapke ghar ke paas paani ya dairy ka source hai.",
        'remedy': "Somwar ko chandrama ko doodh arpit karein."
    }
}

# KP Horary Number Ranges and Meanings
KP_HORARY_RANGES = {
    'immediate_success': (1, 50),
    'short_term_success': (51, 100),
    'medium_term_success': (101, 150),
    'long_term_success': (151, 200),
    'delayed_success': (201, 249)
}

# AstroRemedis Product Suggestions
ASTROREMEDIS_PRODUCTS = {
    'Shani': [
        "AstroRemedis ka Maruti Yantra Kachhua apne ghar me rakhen",
        "AstroRemedis ka Blue Sapphire Bracelet pehenen",
        "AstroRemedis ka Shani Yantra apne workspace par rakhen"
    ],
    'Mangal': [
        "AstroRemedis ka Red Coral Bracelet pehenen",
        "AstroRemedis ka Hanuman Yantra apne ghar me rakhen",
        "AstroRemedis ka Tiger Eye Bracelet pehenen"
    ],
    'Rahu': [
        "AstroRemedis ka Gomed Stone Bracelet pehenen",
        "AstroRemedis ka Rahu Yantra apne ghar me rakhen",
        "AstroRemedis ka Black Tourmaline Bracelet pehenen"
    ],
    'Guru': [
        "AstroRemedis ka Yellow Sapphire Bracelet pehenen",
        "AstroRemedis ka Guru Yantra apne ghar me rakhen",
        "AstroRemedis ka Citrine Bracelet pehenen"
    ],
    'Shukra': [
        "AstroRemedis ka Rose Quartz Bracelet pehenen",
        "AstroRemedis ka Shukra Yantra apne ghar me rakhen",
        "AstroRemedis ka Diamond Bracelet pehenen"
    ],
    'Budh': [
        "AstroRemedis ka Emerald Bracelet pehenen",
        "AstroRemedis ka Budh Yantra apne ghar me rakhen",
        "AstroRemedis ka Green Aventurine Bracelet pehenen"
    ],
    'Surya': [
        "AstroRemedis ka Ruby Bracelet pehenen",
        "AstroRemedis ka Surya Yantra apne ghar me rakhen",
        "AstroRemedis ka Sunstone Bracelet pehenen"
    ],
    'Chandra': [
        "AstroRemedis ka Pearl Bracelet pehenen",
        "AstroRemedis ka Chandra Yantra apne ghar me rakhen",
        "AstroRemedis ka Moonstone Bracelet pehenen"
    ]
}

# Set OpenAI API key
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# Lal Kitab Environment Detection and Chamatkari Tips
def generate_lal_kitab_observation(chart_data):
    """Generate Lal Kitab environment observation based on planetary positions"""
    try:
        planets = chart_data.get('planets', {})
        
        # Find strongest planet (most houses occupied)
        planet_counts = {}
        for house, planet_list in planets.items():
            for planet in planet_list:
                planet_counts[planet] = planet_counts.get(planet, 0) + 1
        
        if planet_counts:
            strongest_planet_code = max(planet_counts.keys(), key=lambda x: planet_counts[x])
            
            # Map planet codes to names
            planet_name_map = {
                'Su': 'Surya', 'Mo': 'Chandra', 'Ma': 'Mangal', 'Me': 'Budh',
                'Ju': 'Guru', 'Ve': 'Shukra', 'Sa': 'Shani', 'Ra': 'Rahu', 'Ke': 'Ketu'
            }
            
            planet_name = planet_name_map.get(strongest_planet_code, strongest_planet_code)
            
            if planet_name in LAL_KITAB_ENVIRONMENT_RULES:
                rule = LAL_KITAB_ENVIRONMENT_RULES[planet_name]
                return {
                    'observation': rule['observation'],
                    'remedy': rule['remedy'],
                    'planet': planet_name,
                    'product_suggestion': ASTROREMEDIS_PRODUCTS.get(planet_name, [])[0] if ASTROREMEDIS_PRODUCTS.get(planet_name) else ""
                }
        
        return None
    except Exception as e:
        logger.error(f"Error generating Lal Kitab observation: {e}")
        return None

def generate_chamatkari_tips(chart_data):
    """Generate additional chamatkari tips based on planetary positions"""
    try:
        planets = chart_data.get('planets', {})
        tips = []
        
        # Check for specific planetary combinations
        for house, planet_list in planets.items():
            if 'Ju' in planet_list and 'Ve' in planet_list:
                tips.append("Ghar ke paas mandir hai to Guru ka aashirwad bana hai.")
            if 'Ra' in planet_list:
                tips.append("Drain ya nala ke karan Rahu ka prabhav hai, isliye aap me sudden success ke yog bante hain.")
            if 'Ve' in planet_list:
                tips.append("Beauty shop ke karan Shukra strong hai, aap naturally attractive vyakti hain.")
            if 'Sa' in planet_list and 'Ju' in planet_list:
                tips.append("Kabootar ya pakshi ke karan Shani-Guru dono sthirta dete hain.")
        
        return tips[:2]  # Return max 2 tips
    except Exception as e:
        logger.error(f"Error generating chamatkari tips: {e}")
        return []

# Generate comprehensive horary responses for follow-up questions
def generate_horary_response(question, user_name=None):
    """Deterministic KP Horary response without generative model.
    Uses internal KP ranges and avoids any information not derived from the horary input.
    """
    if not user_name:
        user_name = 'User'
    try:
        ql = (question or '').lower()
        # Minimal variation strictly based on question category; no invented specifics
        if any(word in ql for word in ['career', 'job', 'naukri', 'business', 'rozi', 'work', 'profession']):
            core = "Career ke sandarbh me KP Horary ke anusar agle kuch mahino me pragati ke sanket milte hain."
        elif any(word in ql for word in ['marriage', 'shadi', 'vivah', 'life partner', 'shaadi']):
            core = "Vivah sambandhi prashn par KP Horary ke anusar samay ke saath sthiti anukul banne ke yog hain."
        elif any(word in ql for word in ['health', 'swasthya', 'bimari', 'illness', 'disease']):
            core = "Swasthya sambandhi prashn par KP Horary ke anusar sudhar ke sanket dikhte hain, par niyamit dekhbhal avashyak hai."
        elif any(word in ql for word in ['money', 'finance', 'wealth', 'prosperity', 'paise', 'dhan']):
            core = "Arthik prashn par KP Horary ke anusar aamdani aur sthirta me krameṇ vriddhi ke yog hain."
        else:
            core = "Prashn ke sandarbh me KP Horary ke anusar sakaratmak parinaamon ki sambhavnayein dikh rahi hain."

        blessing = "Bhagwan aap par apna aashirwad sadaiv banaaye rakhen."
        return sanitize_ai_text(f"- {core}\n- Agar aap horary number batayenge to exact timing batayi ja sakti hai.\n- Yadi aap chahen to main upay bhi batane me madad kar sakta hoon.\n- {blessing}")
    except Exception as e:
        logger.error(f"Error generating horary response: {e}")
        return "KP Horary analysis ke dauran koi samasya aayi. Kripya prashn dobara poochhein."

# KP Horary Analysis for users without birth details
def generate_kp_horary_analysis(horary_number):
    """Generate KP Horary analysis based on the provided number (1-249)"""
    try:
        if not (1 <= horary_number <= 249):
            return None
        
        # Determine success timing based on number range
        timing = "unknown"
        timeframe = "unknown"
        
        for range_name, (start, end) in KP_HORARY_RANGES.items():
            if start <= horary_number <= end:
                if range_name == 'immediate_success':
                    timing = "immediate"
                    timeframe = "1-2 mahine me"
                elif range_name == 'short_term_success':
                    timing = "short_term"
                    timeframe = "3-6 mahine me"
                elif range_name == 'medium_term_success':
                    timing = "medium_term"
                    timeframe = "6-12 mahine me"
                elif range_name == 'long_term_success':
                    timing = "long_term"
                    timeframe = "1-2 saal me"
                elif range_name == 'delayed_success':
                    timing = "delayed"
                    timeframe = "2-3 saal me"
                break
        
        # Generate analysis based on timing
        if timing == "immediate":
            analysis = f"Namaskar, main aapka AstroRemedis ka AI Astrologer hoon. Horary number {horary_number} ke hisab se aapka kaam {timeframe} banne ke yog hain."
        elif timing == "delayed":
            analysis = f"Namaskar, main aapka AstroRemedis ka AI Astrologer hoon. Horary number {horary_number} ke hisab se result positive rahega, bas thoda samay lagega. {timeframe} me success milegi."
        else:
            analysis = f"Namaskar, main aapka AstroRemedis ka AI Astrologer hoon. Horary number {horary_number} ke hisab se aapka kaam {timeframe} banne ke yog hain."
        
        # NO FIXED REMEDY – Only use if KB/observation provides one
        remedy = ""
        blessing = "Bhagwan aap par apna aashirwad sadaiv banaaye rakhen."
        
        return {
            'analysis': analysis,
            'remedy': remedy,
            'blessing': blessing,
            'timing': timing,
            'timeframe': timeframe,
            'horary_number': horary_number
        }
    except Exception as e:
        logger.error(f"Error generating KP Horary analysis: {e}")
        return None

# Mole & Mark Prediction System based on planetary positions
def generate_mole_prediction(chart_data):
    """Generate body mark predictions based on planetary positions"""
    try:
        planets = chart_data.get('planets', {})
        planet_mark_map = {
            'Su': {'body_part': 'chest/neck', 'meaning': 'leadership aur netritva'},
            'Mo': {'body_part': 'face/throat', 'meaning': 'emotion aur sensitivity'},
            'Ma': {'body_part': 'shoulder/hand', 'meaning': 'bravery aur mehnat'},
            'Me': {'body_part': 'leg/back', 'meaning': 'intelligence aur communication'},
            'Ju': {'body_part': 'abdomen', 'meaning': 'fortune aur wisdom'},
            'Ve': {'body_part': 'lips/cheek', 'meaning': 'beauty aur love'},
            'Sa': {'body_part': 'knee/leg', 'meaning': 'stability aur discipline'},
            'Ra': {'body_part': 'ear/neck', 'meaning': 'mystery aur innovation'},
            'Ke': {'body_part': 'spine/back', 'meaning': 'spirituality aur detachment'}
        }
        
        # Find strongest planet (most houses occupied)
        planet_counts = {}
        for house, planet_list in planets.items():
            for planet in planet_list:
                planet_counts[planet] = planet_counts.get(planet, 0) + 1
        
        if planet_counts:
            strongest_planet = max(planet_counts.keys(), key=lambda x: planet_counts[x])
            mark_info = planet_mark_map.get(strongest_planet, {'body_part': 'body', 'meaning': 'special energy'})
            
            return f"Aapke grahon se lagta hai aapke {mark_info['body_part']} par til hai. Ye {strongest_planet} ka prabhav hai jo {mark_info['meaning']} ka pratik hai."
        
        return "Aapke grahon se lagta hai aapke body par koi special nishan hai jo aapki unique energy ko represent karta hai."
    except Exception as e:
        logger.error(f"Error generating mole prediction: {e}")
        return "Aapke grahon se lagta hai aapke body par koi special nishan hai."

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
                "AstroRemedis ka Pyrite Bracelet: Aapke career aur dhan ki growth mein madad karta hai.",
                "AstroRemedis ka Tiger Eye Bracelet: Aapko himmat aur focus deta hai.",
                "AstroRemedis ka Kuber Yantra: Apne desk par rakhein sampannta aur naye avsaron ke liye."
            ],
            "category_name": "Career aur Business"
        },
        "2. Love aur Relationship Remedies 2": {
            "free": "Shukrawar (Friday) ki shaam ko peepal ke ped ko doodh/jal arpit karein (peepal ke ped ko jal dene se rishte mazboot hote hain).",
            "buyable": [
                "AstroRemedis ka Rose Quartz Bracelet: Pyaar aur achhe rishton ko aakarshit karta hai.",
                "AstroRemedis ka Gauri Shankar Rudraksha: Jeevan saathi ke saath bandhan mazboot karta hai.",
                "AstroRemedis ka Shukra Yantra: Ise ghar mein rakhne se partnership ki energy achhi rehti hai."
            ],
            "category_name": "Love aur Relationship"
        },
        "3. Marriage aur Compatibility Remedies 3": {
            "free": "Guruwar (Thursday) ka vrat rakhein ya gau mata ko hara chara khilayein (gair-khati ghass).",
            "buyable": [
                "AstroRemedis ka Rose Quartz Bracelet: Shadi aur achhe rishton mein madad karta hai.",
                "AstroRemedis ka Gauri Shankar Rudraksha: Vivah mein deri door karta hai aur dampatya sukh deta hai.",
                "AstroRemedis ka Shukra Yantra: Prem aur sahayog badhane ke liye use karein."
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

    # AstroRemedis product catalog for optional links/IDs
    product_catalog = {
        "Maruti Yantra Kachhua": {"id": "AR-001", "link": "https://astroremedis.com/product/maruti-yantra-kachhua"},
        "Rose Quartz Bracelet": {"id": "AR-002", "link": "https://astroremedis.com/product/rose-quartz-bracelet"},
        "Pyrite Bracelet": {"id": "AR-003", "link": "https://astroremedis.com/product/pyrite-bracelet"},
        "Tiger Eye Bracelet": {"id": "AR-004", "link": "https://astroremedis.com/product/tiger-eye-bracelet"},
        "Kuber Yantra": {"id": "AR-005", "link": "https://astroremedis.com/product/kuber-yantra"},
        "Gauri Shankar Rudraksha": {"id": "AR-006", "link": "https://astroremedis.com/product/gauri-shankar-rudraksha"},
        "Shukra Yantra": {"id": "AR-007", "link": "https://astroremedis.com/product/shukra-yantra"},
        "Putra Prapti Yantra": {"id": "AR-008", "link": "https://astroremedis.com/product/putra-prapti-yantra"},
        "Haridra Ganesh Yantra": {"id": "AR-009", "link": "https://astroremedis.com/product/haridra-ganesh-yantra"},
        "Moti (Pearl) Stone": {"id": "AR-010", "link": "https://astroremedis.com/product/pearl-stone"},
        "Turquoise Stone": {"id": "AR-011", "link": "https://astroremedis.com/product/turquoise-stone"},
        "Vastu Yantra": {"id": "AR-012", "link": "https://astroremedis.com/product/vastu-yantra"},
        "Red Jasper Bracelet": {"id": "AR-013", "link": "https://astroremedis.com/product/red-jasper-bracelet"},
        "Ganesha Yantra": {"id": "AR-014", "link": "https://astroremedis.com/product/ganesha-yantra"},
        "Blue Sapphire (Neelam)": {"id": "AR-015", "link": "https://astroremedis.com/product/blue-sapphire"},
        "Green Aventurine Bracelet": {"id": "AR-016", "link": "https://astroremedis.com/product/green-aventurine-bracelet"},
        "Shri Yantra": {"id": "AR-017", "link": "https://astroremedis.com/product/shri-yantra"},
        "Citrine Stone": {"id": "AR-018", "link": "https://astroremedis.com/product/citrine-stone"},
        "Amethyst Stone": {"id": "AR-019", "link": "https://astroremedis.com/product/amethyst-stone"},
        "Tulsi Mala": {"id": "AR-020", "link": "https://astroremedis.com/product/tulsi-mala"},
        "Health Yantra": {"id": "AR-021", "link": "https://astroremedis.com/product/health-yantra"},
        "Black Agate Pendant": {"id": "AR-022", "link": "https://astroremedis.com/product/black-agate-pendant"}
    }

    def format_product_line(line: str) -> str:
        """Augment a buyable line with AstroRemedis product link/ID if recognized.
        Keeps tone natural; avoids ad-like phrasing.
        """
        try:
            # Try to find a known product key within the line
            for product_name, meta in product_catalog.items():
                if product_name.lower() in line.lower():
                    suffix_parts = []
                    if meta.get("id"):
                        suffix_parts.append(f"ID: {meta['id']}")
                    if meta.get("link"):
                        suffix_parts.append(meta['link'])
                    if suffix_parts:
                        return f"{line} ({' | '.join(suffix_parts)})"
                    return line
            return line
        except Exception:
            return line

    selected = remedy_map.get(problem_area, remedy_map["8. Health, Energy aur Peace Remedies 8"])
    activation_process = (
        "Apne item ko pehenne se pehle, usey Ganga Jal ya kachche doodh se saaf karein aur dhoop/chaandni mein energize karein. Is dauran 'Om Namah Shivaya' ka 11 baar jaap karein."
    )
    trust_statement = (
        "Main aapko sirf trusted AstroRemedis remedies suggest karta hoon jo siddh aur certified hain."
    )

    if compact:
        paid_one = selected['buyable'][0] if selected.get('buyable') else ''
        paid_one = format_product_line(paid_one) if paid_one else ''
        return (
            f"\n\nAdab ji, ghabrane ki koi baat nahi hai. Yadi aap chahte hain ki aapki problems thik ho ya kuch bhi use kar sakein, uske liye aap yeh upay kar sakte hain:\n\n"
            f"1. {selected['free']}\n"
            f"2. {paid_one} (AstroRemedis pe uplabdh)\n\n"
            f"Activation: {activation_process}\n"
            f"{trust_statement}"
        )
    else:
        # Decorate each buyable with link/ID when available
        decorated = [format_product_line(item) for item in selected['buyable']]
        response = (
            f"\n---\n\n"
            f"{selected['category_name']} ke liye upay:\n"
            f"- Free: {selected['free']}\n"
            f"- Paid options: \n  - " + "\n  - ".join(decorated) + "\n"
            f"- Activation: {activation_process}\n"
            f"- Note: {trust_statement}"
        )
        return response


def should_append_remedies(user_query: str) -> bool:
    """Return True when the user expresses a problem/pain OR asks for a goal-oriented area
    (career, marriage, love, health, finance, property, litigation, child).
    Previously we avoided neutral questions; now we include compact remedies for topical intents too.
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
    topical_markers = [
        'career', 'job', 'naukri', 'business', 'rozi', 'work', 'profession',
        'marriage', 'shadi', 'vivah', 'love', 'pyaar', 'relationship',
        'health', 'swasthya',
        'finance', 'money', 'wealth', 'prosperity', 'paise', 'dhan',
        'property', 'home', 'land', 'dispute',
        'court case', 'litigation', 'case',
        'child', 'santan', 'baby', 'family growth'
    ]
    return any(m in q for m in problem_markers) or any(m in q for m in topical_markers)

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
        """
        Calculates comprehensive chart data.
        Integrates Streamlit's robust logic for Ascendant, Planet-in-House calculation, 
        and Mangal Dosha processing from Prokerala's Planet Position and Mangal Dosha endpoints.
        """
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
        adv_url = "https://api.prokerala.com/v2/astrology/kundli/advanced"
        params = {
            'ayanamsa': 5,
            'coordinates': f"{latitude},{longitude}",
            'datetime': api_datetime_str
        }

        try:
            resp = requests.get(adv_url, headers=headers, params=params, timeout=20)
            # ✨ RECOMMENDED FIX ✨
            resp.raise_for_status()
            raw = resp.json()
            
            # --- START FIX ---
            # 1. Ensure 'raw' is a dict before attempting 'get'
            if not isinstance(raw, dict):
                # If raw is a list (unexpected API response format), wrap it 
                # or handle as a fatal error, but for safety:
                logger.warning("ProKerala raw response was not a dictionary, assuming it's the data payload.")
                raw = {'data': raw}
                
            # 2. Safely get the 'data' payload, defaulting to an empty dict
            data = raw.get('data', {}) 

            # 3. If 'data' is still a list (e.g., raw was a dict but 'data' field 
            #    contained the unexpected list payload), wrap the list correctly.
            if isinstance(data, list):
                logger.warning("ProKerala 'data' field was a list, normalizing into expected dict structure.")
                data = { 'planet_position': { 'planet_position': data } } 
            # --- END FIX ---
        except Exception as e:
            logger.error(f"Error fetching Advanced Kundli: {e}; falling back to mock chart data")
            return self._generate_mock_chart_data(name, dob_date, tob_time, pob_text, latitude, longitude, timezone_str)

        # Robust extraction: different payloads may vary in key names
        planet_positions = (
            (data.get('planet_position') or {}).get('planet_position')
            or data.get('planet_positions')
            or data.get('planets')
            or []
        )
        dasha_periods = data.get('dasha', {}) or data.get('dasha_periods', {})
        mangal_dosha = data.get('mangal_dosha', {})

        planets_in_house = {}
        ascendant_sign = None
        ascendant_sign_name = "N/A"
        planet_code_map = {'Sun': 'Su', 'Moon': 'Mo', 'Mars': 'Ma', 'Mercury': 'Me', 'Jupiter': 'Ju', 'Venus': 'Ve', 'Saturn': 'Sa', 'Rahu': 'Ra', 'Ketu': 'Ke', 'Lagna': 'La'}

        lagna_planet = next((p for p in planet_positions if p.get('id') == 100 or p.get('name') == 'Lagna'), None)
        if lagna_planet:
            ascendant_sign = lagna_planet.get('rasi', {}).get('id')
            ascendant_sign_name = lagna_planet.get('rasi', {}).get('name')

        if ascendant_sign:
            for p in planet_positions:
                rasi_id = p.get('rasi', {}).get('id')
                pname = p.get('name')
                if rasi_id is None or not pname or rasi_id == 0:
                    continue
                house_num = (rasi_id - ascendant_sign + 12) % 12 + 1
                code = planet_code_map.get(pname, pname[:2])
                planets_in_house.setdefault(house_num, [])
                if code and code not in planets_in_house[house_num]:
                    planets_in_house[house_num].append(code)

        for i in range(1, 13):
            planets_in_house.setdefault(i, [])

        # Always fetch planet-position endpoint as a second call to ensure raw positions
        try:
            pos_url = "https://api.prokerala.com/v2/astrology/planet-position"
            pos_resp = requests.get(pos_url, headers=headers, params={
                'ayanamsa': 5,
                'coordinates': f"{latitude},{longitude}",
                'datetime': api_datetime_str
            }, timeout=15)
            if pos_resp.status_code == 200:
                pos_data = pos_resp.json().get('data', {}).get('planet_position', [])
                if pos_data:
                    planet_positions = pos_data
                    # Recompute ascendant and houses from authoritative planet-position
                    if planet_positions:
                        lagna_planet = next((p for p in planet_positions if p.get('id') == 100 or p.get('name') == 'Lagna'), None) or lagna_planet
                        if lagna_planet:
                            ascendant_sign = lagna_planet.get('rasi', {}).get('id')
                            ascendant_sign_name = lagna_planet.get('rasi', {}).get('name')
                        if ascendant_sign:
                            planets_in_house = {}
                            for p in planet_positions:
                                rasi_id = p.get('rasi', {}).get('id')
                                pname = p.get('name')
                                if rasi_id is None or not pname or rasi_id == 0:
                                    continue
                                house_num = (rasi_id - ascendant_sign + 12) % 12 + 1
                                code = planet_code_map.get(pname, pname[:2])
                                planets_in_house.setdefault(house_num, [])
                                if code and code not in planets_in_house[house_num]:
                                    planets_in_house[house_num].append(code)
                            for i in range(1, 13):
                                planets_in_house.setdefault(i, [])
        except Exception as _e:
            logger.warning(f"planet-position fetch failed: {_e}")

        current_mahadasha = dasha_periods.get('mahadasha', {}).get('lord', 'Unknown')

        final_chart_data = {
            "name": name,
            "dob_date": dob_date.strftime('%Y-%m-%d'),
            "tob_time_str": tob_time.strftime('%H:%M:%S'),
            "ascendant_sign": ascendant_sign or 1,
            "ascendant_sign_name": ascendant_sign_name,
            "planets": planets_in_house,
            "birth_location": pob_text,
            "coordinates": {"latitude": latitude, "longitude": longitude},
            "timezone": timezone_str,
            "place": pob_text,
            "dasha_periods": dasha_periods,
            "current_mahadasha": current_mahadasha,
            "mangal_dosha": {
                "is_present": mangal_dosha.get('is_present', False),
                "description": mangal_dosha.get('description', 'Mangal Dosha analysis completed.')
            },
            "prokerala_data": {"planet_positions": planet_positions},
            "is_mock_data": False
        }
        logger.info("✅ Advanced Kundli data processed")
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
            return "Authentic answer unavailable: knowledge base or AI key missing. Kripya birth details dein ya baad me try karein."
            
        try:
            # Ensure variable exists in all code paths
            earliest_marriage_year = 0
            retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})
            relevant_docs = retriever.invoke(question)
            # Concise RAG context (cap total size to avoid token limits)
            raw_docs = "\n\n".join([doc.page_content for doc in relevant_docs])
            context_from_docs = raw_docs[:2000]  # cap to ~2k chars

            # Age calculation for realistic predictions
            dob_date_str = chart_data.get('dob_date')
            dob_date = None
            if isinstance(dob_date_str, str):
                try:
                    dob_date = datetime.strptime(dob_date_str, '%Y-%m-%d').date()
                except:
                    dob_date = datetime(2000, 1, 1).date()
            elif not dob_date:
                dob_date = datetime(2000, 1, 1).date()
            
            current_year = datetime.now().year
            birth_year = dob_date.year
            current_age = current_year - birth_year
            
            # Define minimum realistic ages for prediction categories
            min_ages = {
                "relationship_advice": 21,  
                "career_guidance": 20,  
                "health_guidance": 15,  
                "child_guidance": 22,  
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
            **INTERNAL AGE/LOGIC CONTEXT (CRITICAL - NON-NEGOTIABLE):**
            User was born in {birth_year}. Current Age: {current_age}.  
            **CURRENT YEAR: 2025** - All predictions must be for 2025 onwards.
            Question Type: {response_style}.
            Minimum realistic age for this event is {minimum_age_threshold} years.  
            Prediction year MUST be >= {earliest_realistic_year} AND >= 2025.
            
            **CRITICAL MARRIAGE AGE CHECK:** For marriage predictions, the person must be at least 21 years old (legal age).
            For birth year {birth_year}, the earliest possible marriage year is {earliest_marriage_year}.
            NEVER predict marriage before {earliest_marriage_year} regardless of Dasha data.
            
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

                    mangal = src.get('mangal_dosha') or {}

                    compact = {
                        'name': src.get('name') or 'User',
                        'dob_date': dob_date.strftime('%Y-%m-%d'),
                        'ascendant_sign': src.get('ascendant_sign'),
                        'ascendant_sign_name': src.get('ascendant_sign_name'),
                        'planets': compact_planets,
                        'mangal_dosha': {
                            'is_present': bool(mangal.get('is_present', False)),
                            'description': (mangal.get('description') or '')[:200]
                        },
                        'birth_location': src.get('birth_location'),
                        'coordinates': src.get('coordinates'),
                        'timezone': src.get('timezone')
                    }
                    return compact
                except Exception:
                    return {'name': src.get('name', 'User')}

            compact_chart = build_compact_chart(chart_data or {})
            # Extract user name from chart data
            user_name = compact_chart.get('name', 'User') if isinstance(compact_chart, dict) else 'User'
            
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
            if response_style in ["relationship_advice", "career_guidance", "health_guidance", "child_guidance"]:
                import random
                import time
                
                # Map response styles to follow-up categories
                follow_up_category = {
                    "relationship_advice": "relationship",
                    "career_guidance": "career",  
                    "health_guidance": "health",
                    "child_guidance": "relationship"  # Children questions map to relationship category
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
            
            # Generate mole prediction ONLY if user asked explicitly
            ask_lower = question_lower
            wants_mole = any(k in ask_lower for k in ['mole', 'til', 'nishan', 'daag'])
            mole_prediction = generate_mole_prediction(chart_data) if (chart_data and wants_mole) else ""
            
            # Generate Lal Kitab observation and chamatkari tips
            lal_kitab_observation = generate_lal_kitab_observation(chart_data) if chart_data else None
            chamatkari_tips = generate_chamatkari_tips(chart_data) if chart_data else []

            safe_earliest_marriage_year = earliest_marriage_year or (birth_year + min_ages["relationship_advice"])
            logger.info(f"[AI] response_style={response_style}, earliest_realistic_year={earliest_realistic_year}, earliest_marriage_year={safe_earliest_marriage_year}")

            system_prompt = f"""
            You are AstroRemedis ka AI Astrologer - a divine, scientific, and interactive personality that combines Vedic wisdom with modern technology.
            
            **CORE BEHAVIOUR & PERSONALITY (VARIETY IS KEY):**
            1. **Natural Conversation:** Apne answers ko har baar alag tarike se de. Same question ko alag words me jawab do. Monotonous aur robotic mat lagne dena.
            2. **Flexible Greetings:** Start ko har baar badlte raho:
               - "Namaskar! {user_name} ji"
               - "Pranam! Aapka sawal..."
               - "Achha, dekhaa jaye..."
               - "Haan bilkul, {user_name} ji"
               - Kabhi sirf seedha answer bhi kar sakte ho greeting ke bina
            3. **Natural Responses:** Har reply me 2-4 sentences naturally flow karne chahiye. Fixed template mat use karo. Apne words me natural Hindi-English mix rakho.
            4. **Varied Endings:** Blessing ko har baar alag tarike se de:
               - "Bhagwan aap par apna aashirwad sadaiv banaaye rakhen."
               - "Aapke grah aapko hamesha madad karen."
               - "Mai aasha karta hun aapki sabhi manokamna pure hon."
               - "Bhagwan aap par kripa banaaye rakhen."
               - "May the stars guide you always."
            5. **Conversational Flow:** Jaise insaan baat karta hai waise baat karo. Kabhi thoda pause mat lena, kabhi thoughtful. Natural rhythm maintain karo.
            6. **Language Mix:** Hindi-English naturally mix karo (60-40 ya 70-30, context ke according). Agar naturally English word better hai to use karo.
            7. **Spiritual Words Variety:** Different spiritual words use karo - "aashirwad", "kripa", "prasanna", "shanti", "urja", "grah prabhav", "bhagya", "kismat", "vidhata"
            8. **Human Touch:** Kabhi thoda casual ho jao ("Haan dekhte hain"), kabhi formal ("Kripya batayiye"). Variety rakho.
            
            **VEDIC ASTROLOGY SYSTEM:**
            9. **Technical Details:** DOB, Time & Place input ke base par Lagna, Chandra Rashi, aur Dasha calculate karna
            10. **First Statement:** Pehle AI bole – "Aapki Lagna [Sign] hai, Chandra Rashi [Sign] hai, aur iss samay [Planet] Mahadasha chal rahi hai."
            11. **Dasha Observation:** Dasha ke base par short observation de – "Is samay career me nayi opportunities aa rahi hain par decision carefully lena hoga."
            12. **Human Guess:** AI apne tone me human guess bhi de – "Lagta hai is waqt aap apne kaam ya rishton ko lekar thoda confuse hain."
            13. **Follow-up:** Follow-up hamesha ho – "Kya main aur detail me bataun?"
            14. **Precise Answers:** User ke sawalon ka jawab calculation ke adhar par precise aur warm tone me ho

            IMPORTANT: Agar chart_data me Lagna, Chandra Rashi, aur Dasha available ho to INHE EXACTLY use karo. In teenon ko kabhi change ya guess mat karo. Same DOB ke liye ye hamesha same rahenge.
            
            **MOLE & MARK PREDICTION SYSTEM (Til/Daag/Nishan):**
            15. **Body Mark Reading Layer:** AI apne grahon ke adhar par khud bataye ki user ke sharir ke kis part par til ya daag hone ke yog hain
            16. **Confident Prediction (ON REQUEST ONLY):** Sirf tab likhein jab user ne til/daag ke baare me poocha ho. Location ko region-level (jaise "kandhe/haath") me rakhein; left/right side ka ANDAZA NA lagayein.
            17. **Planet-wise Logic:**
                - Surya → chest/neck (leadership)
                - Chandra → face/throat (emotion)
                - Mangal → shoulder/hand (bravery)
                - Budh → leg/back (intelligence)
                - Guru → abdomen (fortune)
                - Shukra → lips/cheek (beauty)
                - Shani → knee/leg (stability)
                - Rahu → ear/neck (mystery)
                - Ketu → spine/back (spirituality)
            18. **Confirmation Response:** Agar user confirm kare to AI bole – "Ye til aapke grah ki urja ka nishan hai."
            19. **Denial Response:** Agar deny kare to bole – "Ho sakta hai til chhupa ho, lekin grah ka prabhav aapke charitra me dikh raha hai."
            
            **LAL KITAB OBSERVATION & CHAMATKARI TIPS:**
            20. **Environment Detection:** AI khud user ke aas-paas ke environment ke baare me bataaye bina user ke pooche
            21. **Environment Rules:**
                - Shani → hospital, loha, old area
                - Mangal → tailoring, mechanic, iron shop
                - Rahu → drain, mobile tower
                - Guru → school, mandir
                - Shukra → beauty parlour, jewellery
                - Budh → stationery, printing
                - Surya → government office, court
                - Chandra → paani, dairy
            22. **Observation Format:** "Aapke grahon se lagta hai aapke ghar ke paas [environment] hai..."
            23. **Remedy Integration (STRICT):** Agar LAL KITAB OBSERVATION DATA me 'remedy' diya gaya ho to WAHI remedy likhein. Kisi bhi planet ke bina 'Saturday tel daan' jaise generic remedy NA likhein.
            24. **Chamatkari Tips:** "Ghar ke paas mandir hai to Guru ka aashirwad bana hai." (sirf tab jab relevant combinations hon)
            25. **3-Layer Logic:** Detection → Observation → Remedy (all in 2-line response)
            26. **Developer Note:** AI ko environment ke prediction aur remedy dono ek hi 2-line me dene hain
            
            **KP HORARY MODE (Users without DOB/Time):**
            27. **Horary Trigger:** Agar user ke paas janm samay nahi hai to AI bole: "Agar aapko birth details nahi pata to 1 se 249 tak koi number soch kar batayein."
            28. **Horary Analysis:** AI us number ke base par KP Horary chart banaye aur reply de: "Horary number ke hisab se aapka kaam 3 mahine me banne ke yog hain."
            29. **Delay Response:** Agar delay ho to: "Result positive rahega, bas thoda samay lagega."
            30. **Horary Remedy:** Sirf tab upaay dein jab KB/logic me explicitly available ho; generic remedies NA dein.
            31. **Complete Horary Answers:** When in horary mode, provide COMPLETE answers to all questions without asking for birth details. Do not append any labels.
            
            **ASTROREMEDIS BRAND INTEGRATION:**
            33. **Product Suggestions:** Har remedy ke sath AstroRemedis ke product suggestion subtle tarike se aaye: "Shani prashant karne ke liye aap AstroRemedis ka Maruti Yantra Kachhua apne ghar me rakhen."
            34. **Trust Statement:** AI apne tone me बोले "Main aapko sirf trusted AstroRemedis remedies suggest karta hoon jo siddh aur certified hain."
            35. **Natural Integration:** Har suggestion me product ka naam natural tone me include ho, advertisement jaisa nahi lage
            36. **Product Links:** Agar user chahe to direct product link / product ID display ho jaye

            **SYSTEM STRUCTURE SUMMARY:**
            37. **Input Layer** → User ke details ya number
            38. **Detection Layer** → Grah aur house analysis
            39. **Observation Layer** → Lal Kitab aur Mole predictions
            40. **Remedy Layer** → AstroRemedis product + upaay suggestion
            41. **Blessing Layer** → fixed ending line
            
            **VARIETY & NATURALNESS REQUIREMENTS (CRITICAL):**
            42. **EVERY Response MUST Be Different:** Kabhi bhi exact same phrasing mat use karo. Har baar alag words, alag style, alag flow.
            43. **Natural Phrasing:** Template jaisa nahi lagna chahiye. Jaise dost ko phone par baat kar rahe ho, waise natural flow.
            44. **Mix Up Details:** Kabhi technical details pehle do, kabhi end mein. Kabhi bolte-bolte explain karo, kabhi seedha answer.
            45. **Conversational Length:** 3-5 sentences naturally flow karein. Kya bolna hai wo decide karo, but naturally.
            46. **Unique Each Time:** Agar same question puchha jaye to har baar alag angle se jawab do. Kya user ko pata nahi hai repeat ho raha hai.
            47. **Emotional Range:** Kabhi happy ("Bahut acchi baat hai!"), kabhi concerned ("Dekhte hain"), kabhi excited ("Achha sawal hai!"). Feelings naturally vary karo.

            **CRITICAL ACCURACY & LOGIC RULES:**
            48. **STRICT GROUNDING (NON-NEGOTIABLE):** Sirf "INTERNAL REFERENCE DATA" (chart data) aur "KP ASTROLOGY KNOWLEDGE" (docs) ka hi upyog karein. Agar context me jo baat NAHI hai, to seedha kahe: "Is vishay par pakki jaankari uplabdh nahi hai." Koi bhi fact invent NA karein.
            49. **CURRENT YEAR AWARENESS:** We are currently in 2025. ALL predictions must be for FUTURE years (2025 onwards)
            50. **AGE/LOGIC OVERRIDE:** For any prediction, the Prediction Year MUST be GREATER THAN or EQUAL TO the Earliest Realistic Year ({earliest_realistic_year})
            51. **MARRIAGE AGE VALIDATION:** For marriage predictions, the person must be at least 21 years old. For birth year {birth_year}, the earliest possible marriage year is {earliest_marriage_year}
            52. **Dasha Priority:** The timing for prediction MUST be sourced from the Dasha periods
            53. **Time Reference:** ALWAYS use specific FUTURE years/timeframes derived from the Dasha data
            54. **Technical Query Handling:** When users ask for technical details, provide specific information with clear explanations
            55. **REMEDY INSTRUCTION:** If remedies are provided, include them in your main response as plain text before the spiritual blessing. NEVER use markdown formatting like **bold** or *italic* - use only plain text.

            **RESPONSE FORMAT (STRICT):**
            Output EXACTLY 5 short lines (no labels), one per line, in this order:
            1) Greeting line
            2) Core Line 1 (Vedic/KP + optional mole/guess)
            3) Core Line 2 (Lal Kitab + remedy + subtle product)
            4) Follow-up (short question)
            5) Blessing line
            Example (no labels):
            Namaskar, main aapka AstroRemedis ka AI Astrologer hoon.
            Aapki Lagna [Sign] hai... (ya Horary number ...)
            Aapke grahon se... AstroRemedis ka ... beneficial hoga.
            Kya main aur detail me bataun?
            Bhagwan aap par apna aashirwad sadaiv banaaye rakhen.

            **User's Question:** "{question}"

            **INTERNAL REFERENCE DATA (Analyze and Apply Rules):**
            {chart_context}
            
            **HORARY MODE DETECTION:** If chart_data contains mode: 'horary', you are in KP Horary mode. Provide complete answers without asking for birth details.
            
            **MOLE PREDICTION DATA:** {mole_prediction}
            
            **LAL KITAB OBSERVATION DATA:** {json.dumps(lal_kitab_observation, ensure_ascii=False) if lal_kitab_observation else "None"}
            IF lal_kitab_observation provides 'remedy' AND 'planet', you MUST use that EXACT remedy string and NO OTHER. This is mandatory.
            
            **CHAMATKARI TIPS DATA:** {json.dumps(chamatkari_tips, ensure_ascii=False) if chamatkari_tips else "None"}
            
            **KP ASTROLOGY KNOWLEDGE (Internal Reference Only):**
            {context_from_docs}
            
            {age_logic_context}

            **CRITICAL INSTRUCTION - READ CAREFULLY:** 
            You MUST make every response feel fresh, natural, and conversational. NO templates, NO repetition. Imagine you're talking to a friend - be warm, be real, be natural. Vary your greetings, mix your sentence structure, change your phrasing every single time. Make the user feel like they're talking to a REAL person, not a robot reciting scripts. Keep it spiritual but human, accurate but natural. NEVER repeat the exact same words for similar questions. BE CONVERSATIONAL, BE HUMAN.
            Formatting rules: Start each bullet on a new line beginning with '- '. Avoid numbering unless needed. Keep 3–5 short bullets total.
            {('MANDATORY: You MUST include these EXACT remedies in your response as plain text (copy them exactly, including the natural empathetic introduction): ' + remedies_section) if remedies_section else ''}
            {follow_up_instruction if follow_up_instruction else ''}
                            """
            
            try:
                response = openai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": system_prompt + "\n\nRespond in 3–5 short bullet points, max ~120 words. If information is missing from INTERNAL REFERENCE DATA or KP docs, say it is not available. Avoid physical feature claims unless explicitly asked. Be crisp."}],
                    temperature=0.2,
                    max_tokens=260,
                    frequency_penalty=0.4,
                    presence_penalty=0.2,
                    timeout=12
                )
                return sanitize_ai_text(response.choices[0].message.content.strip())
            except Exception as primary_error:
                try:
                    short_prompt = system_prompt
                    if len(short_prompt) > 6000:
                        short_prompt = short_prompt[:6000]
                    response = openai.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": short_prompt + "\n\nKeep it to 3–5 concise bullets (<=120 words)."}],
                        temperature=0.6,
                        max_tokens=220,
                        timeout=10
                    )
                    return sanitize_ai_text(response.choices[0].message.content.strip())
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
            # No generic fallbacks – require chart/KB for authenticity
            if not chart_data:
                return "Authentic uttar ke liye janm ke vivran (DOB, time, place) ya horary number (1–249) avashyak hai. Kripya ye jaankari dein."
            if not (self.vector_store and OPENAI_API_KEY):
                return "Authentic uttar ke liye knowledge base/AI uplabdh nahi hai. Kripya thodi der baad try karein."
    
    def _get_basic_response(self, user_message):
        """Basic astrology response when RAG is not available"""
        user_message_lower = user_message.lower()
        
        # Check for KP Horary mode trigger
        if any(phrase in user_message_lower for phrase in [
            'birth details nahi', 'janm samay nahi', 'birth time nahi', 
            'dob nahi', 'time of birth nahi', 'birth details nahi pata'
        ]):
            return "Agar aapko birth details nahi pata to 1 se 249 tak koi number soch kar batayein. Main us number ke base par KP Horary chart banake aapka analysis karunga."
        
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
        "version": "2.0.0 (Final Logic Integrated)",
        "features": [
            "RAG (Retrieval Augmented Generation)",
            "LangChain Integration",
            "Mangal Dosha Calculation",
            "Advanced AI Responses",
            "Timezone Support",
            "Lal Kitab Environment Detection",
            "KP Horary Analysis",
            "Chamatkari Tips",
            "AstroRemedis Product Integration"
        ],
        "endpoints": {
            "chat": "/api/chat",
            "kundli": "/api/kundli",
            "analyze": "/api/analyze",
            "health": "/api/health",
            "kp-horary": "/api/kp-horary",
            "lal-kitab": "/api/lal-kitab"
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
        client_profile = data.get('client_profile') or {}
        suppress_identities = bool(client_profile.get('introduced_core_facts'))
        
        if not user_message:
            return jsonify({
                "error": "Message is required"
            }), 400
        
        # Check if we're in horary mode
        if chart_data and chart_data.get('mode') == 'horary':
            # Use horary-specific response generator
            user_name = chart_data.get('name', 'User')
            ai_response = generate_horary_response(user_message, user_name)
        else:
            # Prefer detailed Kundli data; if only chart or missing positions, try to refresh
            enriched = chart_data or {}
            positions = (enriched.get('prokerala_data') or {}).get('planet_positions')
            has_positions = bool(positions)
            has_houses = bool(enriched.get('planets'))
            if not (has_positions and has_houses):
                try:
                    name = enriched.get('name') or 'User'
                    dob_str = enriched.get('dob_date')
                    tob_str = enriched.get('tob_time_str')
                    place = enriched.get('birth_location') or enriched.get('place') or ''
                    tz = enriched.get('timezone') or 'Asia/Kolkata'
                    coords = enriched.get('coordinates') or {}
                    lat = coords.get('latitude')
                    lon = coords.get('longitude')
                    if dob_str and tob_str and place and (lat is not None) and (lon is not None):
                        dob_date = datetime.strptime(dob_str, '%Y-%m-%d').date()
                        tob_time = datetime.strptime(tob_str, '%H:%M:%S').time()
                        # Attempt refresh via advanced Kundli
                        enriched = astro_api.calculate_chart_data(name, dob_date, tob_time, place, lat, lon, tz) or enriched
                except Exception as _e:
                    pass

            ai_response = astro_api.generate_ai_response(user_message, enriched)

        # Enforce stable identities and suppress repeats after first reply
        ai_response = enforce_identity_consistency(
            ai_response,
            {
                'lagna': client_profile.get('lagna'),
                'chandra_rashi': client_profile.get('chandra_rashi'),
                'mahadasha': client_profile.get('mahadasha')
            },
            suppress_identities=suppress_identities
        )
        
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
        
        # Always fetch visual chart SVG as well so frontend has both JSON and SVG
        visual_chart = astro_api.generate_chart_only(
            birth_data['name'],
            birth_data['dob_date'],
            birth_data['tob_time'],
            birth_data['place'],
            latitude,
            longitude,
            birth_data['timezone']
        )

        payload = {
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
        if visual_chart:
            payload["visual_chart"] = visual_chart
        return jsonify(payload)
        
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

@app.route('/api/kp-horary', methods=['POST'])
def kp_horary_analysis():
    """KP Horary analysis endpoint for users without birth details"""
    try:
        data = request.get_json()
        horary_number = data.get('horary_number')
        
        if not horary_number:
            return jsonify({
                "error": "Horary number is required (1-249)"
            }), 400
        
        try:
            horary_number = int(horary_number)
        except ValueError:
            return jsonify({
                "error": "Horary number must be a valid integer"
            }), 400
        
        if not (1 <= horary_number <= 249):
            return jsonify({
                "error": "Horary number must be between 1 and 249"
            }), 400
        
        # Generate KP Horary analysis
        analysis = generate_kp_horary_analysis(horary_number)
        
        if not analysis:
            return jsonify({
                "error": "Failed to generate horary analysis"
            }), 500
        
        return jsonify({
            "success": True,
            "analysis": analysis,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in KP Horary endpoint: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500

@app.route('/api/lal-kitab', methods=['POST'])
def lal_kitab_analysis():
    """Lal Kitab environment observation endpoint"""
    try:
        data = request.get_json()
        chart_data = data.get('chart_data')
        
        if not chart_data:
            return jsonify({
                "error": "Chart data is required for Lal Kitab analysis"
            }), 400
        
        # Generate Lal Kitab observation
        observation = generate_lal_kitab_observation(chart_data)
        chamatkari_tips = generate_chamatkari_tips(chart_data)
        
        return jsonify({
            "success": True,
            "observation": observation,
            "chamatkari_tips": chamatkari_tips,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in Lal Kitab endpoint: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500

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