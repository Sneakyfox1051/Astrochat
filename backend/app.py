import os
import warnings
import re
import json
import logging
import random
from datetime import datetime, timedelta
import pytz

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv

# Conditional Imports - Handle missing dependencies gracefully
try:
    from googleapiclient.errors import HttpError
    # NOTE: The actual google_sheets.py file is assumed to exist outside this file
    # and contain append_form_submission and diagnose_connection functions.
    from google_sheets import append_form_submission, diagnose_connection
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    append_form_submission = None
    diagnose_connection = None
    GOOGLE_SHEETS_AVAILABLE = False
    
try:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
    GEOPY_AVAILABLE = True
except ImportError:
    class MockGeocoder:
        def geocode(self, *args, **kwargs):
            return None
    Nominatim = MockGeocoder
    GEOPY_AVAILABLE = False

try:
    # LangChain imports
    from langchain_community.document_loaders import Docx2txtLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import Chroma
    import openai
    RAG_AVAILABLE = True
except ImportError as e:
    import openai
    RAG_AVAILABLE = False


# --- 1. Configuration and Constants ---

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

os.environ['CHROMA_TELEMETRY'] = 'false'
warnings.filterwarnings('ignore', category=UserWarning, module='onnxruntime')

# Load environment variables
ENV_PATH = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(ENV_PATH, override=True)

def get_env(key, default=None):
    return os.getenv(key, default)

PROKERALA_CLIENT_ID = get_env('PROKERALA_CLIENT_ID')
PROKERALA_CLIENT_SECRET = get_env('PROKERALA_CLIENT_SECRET')
OPENAI_API_KEY = get_env('OPENAI_API_KEY')
GOOGLE_SHEETS_SPREADSHEET_NAME = get_env('GOOGLE_SHEETS_SPREADSHEET_NAME', 'AstroRemedis Data')
GOOGLE_SHEETS_WORKSHEET_NAME = get_env('GOOGLE_SHEETS_WORKSHEET_NAME', 'Sheet1')

DOC_FILES = ["KP_RULE_1.docx", "KP_RULE_2.docx", "KP_RULE_3.docx", "Laal KItab.docx"]
DEFAULT_LAT, DEFAULT_LON = 19.0760, 72.8777
DEFAULT_TZ = 'Asia/Kolkata'
OPENAI_MODEL = "gpt-4o-mini" # Using the fast, cost-effective model

if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
else:
    logger.warning("OpenAI API key not found - AI features will be limited/disabled.")

# Static Data for Logic Layers
LAL_KITAB_ENVIRONMENT_RULES = {
    'Shani': {'triggers': ['hospital', 'loha', 'old area', 'iron', 'metal', 'construction'], 'observation': "Aapke grahon se lagta hai aapke ghar ke paas hospital ya darji ki dukaan hai.", 'remedy': "Saturday ko tel daan karen, Shani prasann rahenge."},
    'Mangal': {'triggers': ['tailoring', 'mechanic', 'iron shop', 'garage', 'workshop', 'cutting'], 'observation': "Aapke grahon se lagta hai aapke ghar ke paas tailoring ya mechanic ki dukaan hai.", 'remedy': "Mangalwar ko hanuman chalisa ka path karein."},
    'Rahu': {'triggers': ['drain', 'mobile tower', 'nala', 'sewer', 'telecom', 'antenna'], 'observation': "Aapke grahon se lagta hai aapke ghar ke paas drain ya mobile tower hai.", 'remedy': "Rahu ke liye coconut daan karein."},
    'Guru': {'triggers': ['school', 'mandir', 'temple', 'college', 'education', 'religious'], 'observation': "Aapke grahon se lagta hai aapke ghar ke paas school ya mandir hai.", 'remedy': "Guruwar ko gau mata ko hara chara khilayein."},
    'Shukra': {'triggers': ['beauty parlour', 'jewellery', 'cosmetics', 'fashion', 'salon'], 'observation': "Aapke grahon se lagta hai aapke ghar ke paas beauty parlour ya jewellery shop hai.", 'remedy': "Shukrawar ko peepal ke ped ko doodh arpit karein."},
    'Budh': {'triggers': ['stationery', 'printing', 'book', 'paper', 'office supplies'], 'observation': "Aapke grahon se lagta hai aapke ghar ke paas stationery ya printing shop hai.", 'remedy': "Budhwar ko green moong daal daan karein."},
    'Surya': {'triggers': ['government office', 'court', 'police', 'administration', 'official'], 'observation': "Aapke grahon se lagta hai aapke ghar ke paas government office ya court hai.", 'remedy': "Ravivar ko copper ke bartan se Surya Dev ko jal arpit karein."},
    'Chandra': {'triggers': ['paani', 'dairy', 'water', 'milk', 'pond', 'lake'], 'observation': "Aapke grahon se lagta hai aapke ghar ke paas paani ya dairy ka source hai.", 'remedy': "Somwar ko chandrama ko doodh arpit karein."}
}
KP_HORARY_RANGES = {
    'immediate_success': (1, 50), 'short_term_success': (51, 100), 'medium_term_success': (101, 150),
    'long_term_success': (151, 200), 'delayed_success': (201, 249)
}
ASTROREMEDIS_PRODUCTS = {
    'Shani': ["AstroRemedis ka Maruti Yantra Kachhua apne ghar me rakhen", "AstroRemedis ka Blue Sapphire Bracelet pehenen", "AstroRemedis ka Shani Yantra apne workspace par rakhen"],
    'Mangal': ["AstroRemedis ka Red Coral Bracelet pehenen", "AstroRemedis ka Hanuman Yantra apne ghar me rakhen", "AstroRemedis ka Tiger Eye Bracelet pehenen"],
    'Rahu': ["AstroRemedis ka Gomed Stone Bracelet pehenen", "AstroRemedis ka Rahu Yantra apne ghar me rakhen", "AstroRemedis ka Black Tourmaline Bracelet pehenen"],
    'Guru': ["AstroRemedis ka Yellow Sapphire Bracelet pehenen", "AstroRemedis ka Guru Yantra apne ghar me rakhen", "AstroRemedis ka Citrine Bracelet pehenen"],
    'Shukra': ["AstroRemedis ka Rose Quartz Bracelet pehenen", "AstroRemedis ka Shukra Yantra apne ghar me rakhen", "AstroRemedis ka Diamond Bracelet pehenen"],
    'Budh': ["AstroRemedis ka Emerald Bracelet pehenen", "AstroRemedis ka Budh Yantra apne ghar me rakhen", "AstroRemedis ka Green Aventurine Bracelet pehenen"],
    'Surya': ["AstroRemedis ka Ruby Bracelet pehenen", "AstroRemedis ka Surya Yantra apne ghar me rakhen", "AstroRemedis ka Sunstone Bracelet pehenen"],
    'Chandra': ["AstroRemedis ka Pearl Bracelet pehenen", "AstroRemedis ka Chandra Yantra apne ghar me rakhen", "AstroRemedis ka Moonstone Bracelet pehenen"]
}
PRODUCT_CATALOG = {
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


# --- 2. Helper Functions ---

def sanitize_ai_text(text: str) -> str:
    """Sanitizes and enforces a hard length cap on AI generated text."""
    try:
        if not text: return ""
        cleaned = str(text)
        patterns = [r"\$\([^\)]*\)", r"</?script[^>]*>", r"[{}();<>]{2,}", r"#[A-Za-z0-9_-]+\([^)]*\)",]
        for pat in patterns: cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
        cleaned = re.sub(r"[•\u2022\u2023\u2043\u2219\u25E6\u204C\u204D\u2219]+\s*", "- ", cleaned)
        cleaned = re.sub(r"(?m)(?<!^)(?:\s)+- ", "\n- ", cleaned)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        
        # Enforce strict 5-line limit (for consistency with prompt output)
        lines = cleaned.split('\n')
        if len(lines) > 5:
            cleaned = '\n'.join(lines[:5])
        
        # Hard length cap for safety
        if len(cleaned) > 900:
            cleaned = cleaned[:900]
            last_period = cleaned.rfind('.')
            if last_period > 700: cleaned = cleaned[:last_period + 1]
        return cleaned
    except Exception: return text

def enforce_identity_consistency(text: str, profile: dict = None, suppress_identities: bool = False) -> str:
    """Ensures Lagna, Rashi, and Dasha are consistently presented based on chart data."""
    if not text: return text
    try:
        t = text.replace("\r\n", "\n").replace("\r", "\n")
        if profile:
            def sub_identity(label, value):
                nonlocal t
                if not value: return
                if label == 'lagna': patterns = [r"(?im)^(?:lagna|ascendant)\s*[:\-]\s*.+$", r"(?i)(lagna|ascendant)\b[^\n]*"]
                elif label == 'chandra_rashi': patterns = [r"(?im)^(?:chandra\s*rashi|moon\s*sign|moonsign)\s*[:\-]\s*.+$", r"(?i)(chandra\s*rashi|moon\s*sign|moonsign)\b[^\n]*"]
                elif label == 'mahadasha': patterns = [r"(?im)^(?:maha\s*dasha|mahadasha|current\s*dasha)\s*[:\-]\s*.+$", r"(?i)(maha\s*dasha|mahadasha|current\s*dasha)\b[^\n]*"]
                else: return
                replacement = f"{label.replace('_', ' ').title()} {value}"
                for pat in patterns: t = re.sub(pat, replacement, t)

            sub_identity('lagna', profile.get('lagna'))
            sub_identity('chandra_rashi', profile.get('chandra_rashi'))
            sub_identity('mahadasha', profile.get('mahadasha'))
        
        t = re.sub(r"(?i)\bmoonsign\b", "Moon sign", t)

        if profile and profile.get('mahadasha'):
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
    except Exception: return text

def generate_lal_kitab_observation(chart_data):
    """Generates Lal Kitab environment observation and specific remedy based on strongest planet."""
    try:
        planets = chart_data.get('planets', {})
        planet_counts = {}
        for house, planet_list in planets.items():
            for planet in planet_list: planet_counts[planet] = planet_counts.get(planet, 0) + 1
        
        if planet_counts:
            # Exclude Lagna/Ketu/Rahu for strongest planet determination to focus on natal planets
            planet_counts_filtered = {k: v for k, v in planet_counts.items() if k not in ['La', 'Ke', 'Ra']}
            if not planet_counts_filtered: # Fallback to include all if natal planets are sparse
                 planet_counts_filtered = planet_counts
                 
            strongest_planet_code = max(planet_counts_filtered.keys(), key=lambda x: planet_counts_filtered[x])
            
            planet_name_map = {'Su': 'Surya', 'Mo': 'Chandra', 'Ma': 'Mangal', 'Me': 'Budh', 'Ju': 'Guru', 'Ve': 'Shukra', 'Sa': 'Shani', 'Ra': 'Rahu', 'Ke': 'Ketu'}
            planet_name = planet_name_map.get(strongest_planet_code, strongest_planet_code)
            
            if planet_name in LAL_KITAB_ENVIRONMENT_RULES:
                rule = LAL_KITAB_ENVIRONMENT_RULES[planet_name]
                product_suggestion_base = random.choice(ASTROREMEDIS_PRODUCTS.get(planet_name, [""])).split(':')[0]
                return {
                    'observation': rule['observation'],
                    'remedy': rule['remedy'],
                    'planet': planet_name,
                    'product_suggestion': product_suggestion_base
                }
        return None
    except Exception as e:
        logger.error(f"Error generating Lal Kitab observation: {e}")
        return None

def generate_mole_prediction(chart_data):
    """Generates a body mark prediction based on the strongest planet (Rule 4)."""
    try:
        planets = chart_data.get('planets', {})
        planet_mark_map = {
            'Su': {'body_part': 'chest/neck', 'meaning': 'leadership aur netritva', 'planet_name': 'Surya'},
            'Mo': {'body_part': 'face/throat', 'meaning': 'emotion aur sensitivity', 'planet_name': 'Chandra'},
            'Ma': {'body_part': 'shoulder/hand', 'meaning': 'bravery aur mehnat', 'planet_name': 'Mangal'},
            'Me': {'body_part': 'leg/back', 'meaning': 'intelligence aur communication', 'planet_name': 'Budh'},
            'Ju': {'body_part': 'abdomen', 'meaning': 'fortune aur wisdom', 'planet_name': 'Guru'},
            'Ve': {'body_part': 'lips/cheek', 'meaning': 'beauty aur love', 'planet_name': 'Shukra'},
            'Sa': {'body_part': 'knee/leg', 'meaning': 'stability aur discipline', 'planet_name': 'Shani'},
            'Ra': {'body_part': 'ear/neck', 'meaning': 'mystery aur innovation', 'planet_name': 'Rahu'},
            'Ke': {'body_part': 'spine/back', 'meaning': 'spirituality aur detachment', 'planet_name': 'Ketu'}
        }
        planet_counts = {}
        for house, planet_list in planets.items():
            for planet in planet_list: planet_counts[planet] = planet_counts.get(planet, 0) + 1
        
        if planet_counts:
            strongest_planet = max(planet_counts.keys(), key=lambda x: planet_counts[x])
            mark_info = planet_mark_map.get(strongest_planet, {'body_part': 'body', 'meaning': 'special energy', 'planet_name': 'Strong Grah'})
            
            return f"Aapke grahon se lagta hai aapke **{mark_info['body_part']}** par **til** hai. Ye **{mark_info['planet_name']}** ka prabhav hai jo **{mark_info['meaning']}** ka pratik hai."
        
        return "Aapke grahon se lagta hai aapke body par koi special nishan hai jo aapki unique energy ko represent karta hai."
    except Exception as e:
        logger.error(f"Error generating mole prediction: {e}")
        return "Aapke grahon se lagta hai aapke body par koi special nishan hai."
    
def generate_horary_response(horary_number, question, user_name):
    """KP Horary response adhering to the strict 5-line format (Rule 5)."""
    try:
        timing = "unknown"; timeframe = "unknown"
        for range_name, (start, end) in KP_HORARY_RANGES.items():
            if start <= horary_number <= end:
                if range_name == 'immediate_success': timeframe = "1-2 mahine me"; timing = "immediate"
                elif range_name == 'short_term_success': timeframe = "3-6 mahine me"; timing = "short_term"
                elif range_name == 'medium_term_success': timeframe = "6-12 mahine me"; timing = "medium_term"
                elif range_name == 'long_term_success': timeframe = "1-2 saal me"; timing = "long_term"
                elif range_name == 'delayed_success': timeframe = "2-3 saal me"; timing = "delayed"
                break
        
        GREETING = "Namaskar, main aapka AstroRemedis ka AI Astrologer hoon."
        BLESSING = "Bhagwan aap par apna aashirwad sadaiv banaaye rakhen."
        FOLLOW_UP = "Kya main aur detail me bataun?"
        
        if timing == "immediate":
            CORE_1 = f"Horary number {horary_number} ke hisab se aapka kaam {timeframe} banne ke yog hain. Lagta hai aap is vishay ko lekar bahut excited hain."
        elif timing == "delayed":
            CORE_1 = f"Horary number {horary_number} ke hisab se result positive rahega, bas thoda samay lagega. **{timeframe}** me success milegi."
        else:
            CORE_1 = f"Horary number {horary_number} ke hisab se aapka kaam {timeframe} banne ke yog hain. Aapka sawal important hai."

        REMEDY_PLANET = 'Shani'
        if timing in ["delayed", "long_term"]:
            PRODUCT_SUGG = random.choice(ASTROREMEDIS_PRODUCTS['Shani']).split(':')[0]
            CORE_2 = f"Shani prabhav me hai, isliye **Shanivar ko tel daan** karna shubh rahega. **Shani shanti** ke liye aap **{PRODUCT_SUGG}** use kar sakte hain."
        else:
            PRODUCT_SUGG = random.choice(ASTROREMEDIS_PRODUCTS['Guru']).split(':')[0]
            CORE_2 = f"Guru ki kripa se aapka samay theek hai. Apne **Vishwas** ko mazboot rakhiye. **{PRODUCT_SUGG}** aapke Bhagya ko aur badhayega."

        response = f"{GREETING}\n{CORE_1}\n{CORE_2}\n{FOLLOW_UP}\n{BLESSING}"
        return sanitize_ai_text(response)

    except Exception as e:
        logger.error(f"Error generating KP Horary response: {e}")
        return "KP Horary analysis ke dauran koi samasya aayi. Kripya prashn dobara poochhein. Bhagwan aap par apna aashirwad sadaiv banaaye rakhen."

# --- Helper Functions (Remaining original logic) ---
def get_coordinates(place_name):
    # ... (Original geocoding logic)
    if not GEOPY_AVAILABLE: return DEFAULT_LAT, DEFAULT_LON
    geolocator = Nominatim(user_agent="astrobot_app")
    try:
        location = geolocator.geocode(place_name, timeout=5) 
        if location: return location.latitude, location.longitude
    except (GeocoderTimedOut, GeocoderUnavailable) as e:
        logger.warning(f"Geocoding failed for '{place_name}': {e}. Using default.")
    except Exception as e:
        logger.error(f"Unknown Geocoding error for '{place_name}': {e}. Using default.")
    return DEFAULT_LAT, DEFAULT_LON

def parse_birth_data(data):
    # ... (Original data parsing logic)
    try:
        name = data.get('name', data.get('full_name', data.get('person_name', ''))).strip()
        dob_str = data.get('dob', data.get('date_of_birth', data.get('birth_date', data.get('birthday', ''))))
        tob_str = data.get('tob', data.get('time_of_birth', data.get('birth_time', data.get('time', ''))))
        place = data.get('place', data.get('birth_place', data.get('location', data.get('city', ''))))
        timezone_str = data.get('timezone', data.get('tz', DEFAULT_TZ))
        
        if not name or not dob_str or not tob_str or not place: raise ValueError(f"Required fields missing.")
        
        dob_date = None
        date_formats = ['%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d', '%d.%m.%Y', '%m.%d.%Y', '%d %m %Y', '%B %d, %Y', '%d %B %Y']
        for fmt in date_formats:
            try: dob_date = datetime.strptime(dob_str.strip(), fmt).date(); break
            except ValueError: continue
        if dob_date is None: raise ValueError(f"Unable to parse date: {dob_str}")
        
        tob_time = None
        time_formats = ['%H:%M:%S', '%H:%M', '%I:%M:%S %p', '%I:%M %p', '%I:%M:%S %p', '%I:%M %p']
        for fmt in time_formats:
            try: tob_time = datetime.strptime(tob_str.strip(), fmt).time(); break
            except ValueError: continue
        if tob_time is None: raise ValueError(f"Unable to parse time: {tob_str}")
        
        return {'name': name, 'dob_date': dob_date, 'tob_time': tob_time, 'place': place.strip(), 'timezone': timezone_str}
        
    except Exception as e:
        logger.error(f"Error parsing birth data: {e}")
        raise ValueError(f"Data parsing error: {str(e)}")

# Placeholder functions not used in final logic but required by old structure
def should_append_remedies(user_query: str) -> bool: return False
def generate_remedies(user_query, chart_data, compact=False): return ""

class CustomOpenAIEmbeddings:
    """Custom OpenAI embeddings class for RAG."""
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = openai.OpenAI(api_key=api_key)
    def embed_documents(self, texts):
        try:
            response = self.client.embeddings.create(model="text-embedding-3-small", input=texts)
            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            logger.error(f"Error embedding documents: {e}")
            return [[0.0] * 1536 for _ in texts] 
    def embed_query(self, text):
        try:
            response = self.client.embeddings.create(model="text-embedding-3-small", input=[text])
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error embedding query: {e}")
            return [0.0] * 1536

# --- 3. Main Logic Class (UPDATED for /kundli/advanced) ---

class EnhancedAstroBotAPI:
    
    def __init__(self):
        self.access_token = None
        self.token_expiry = None
        self.vector_store = None
        self.prokerala_enabled = bool(PROKERALA_CLIENT_ID and PROKERALA_CLIENT_SECRET)
        if RAG_AVAILABLE and OPENAI_API_KEY: self._load_vector_store()
        else: logger.info("RAG system disabled - Dependencies or API key missing.")

    def _get_access_token(self):
        # ... (Token logic remains the same) ...
        if not self.prokerala_enabled: return None
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry: return self.access_token
        token_url = "https://api.prokerala.com/token"
        data = {"grant_type": "client_credentials", "client_id": PROKERALA_CLIENT_ID, "client_secret": PROKERALA_CLIENT_SECRET}
        try:
            response = requests.post(token_url, data=data, timeout=15)
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data["access_token"]
            expires_in = token_data.get('expires_in', 3600)
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 300) 
            return self.access_token
        except requests.exceptions.RequestException as e:
            logger.error(f"Prokerala Token Request Failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unknown Error during Prokerala Token request: {e}")
            return None

    def _load_vector_store(self):
        # ... (RAG/Vector store loading remains the same) ...
        try:
            embeddings = CustomOpenAIEmbeddings(OPENAI_API_KEY)
            persist_directory = "./chroma_db"
            if os.path.exists(persist_directory):
                try:
                    self.vector_store = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
                    if self.vector_store._collection.count() > 0: return
                    else: logger.info("ChromaDB found but empty. Rebuilding...")
                except Exception as e: logger.warning(f"Error loading existing ChromaDB: {e}. Rebuilding...")

            all_docs = []
            docs_path = os.path.join(os.path.dirname(__file__), '..', 'docs')
            for doc_file in DOC_FILES:
                file_path = os.path.join(docs_path, doc_file)
                if os.path.exists(file_path):
                    try:
                        loader = Docx2txtLoader(file_path)
                        all_docs.extend(loader.load())
                    except Exception as e: logger.error(f"Error loading {doc_file}: {e}")
                else: logger.warning(f"Document file not found at {file_path}")

            if all_docs:
                text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
                texts = text_splitter.split_documents(all_docs)
                self.vector_store = Chroma.from_documents(documents=texts, embedding=embeddings, persist_directory=persist_directory)
            else:
                logger.warning("No documents loaded or OpenAI API key missing")
        except Exception as e:
            logger.error(f"FATAL Error loading vector store: {e}")
            self.vector_store = None

    def _generate_mock_chart_data(self, name, dob_date, tob_time, pob_text, latitude, longitude, timezone_str):
        # ... (Mock data generation remains the same) ...
        planets_in_house = {str(i): [] for i in range(1, 13)}
        planet_codes = ['Su', 'Mo', 'Ma', 'Me', 'Ju', 'Ve', 'Sa', 'Ra', 'Ke']
        assigned_planets = random.sample(planet_codes, random.randint(3, 7))
        for planet in assigned_planets:
            house = random.randint(1, 12)
            planets_in_house[str(house)].append(planet)
        ascendant_signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
        ascendant_sign = random.randint(1, 12)
        ascendant_sign_name = ascendant_signs[ascendant_sign - 1]
        mangal_dosha_present = random.random() < 0.3
        dasha_list = ['Shani', 'Guru', 'Mangal', 'Rahu', 'Budh', 'Shukra', 'Surya', 'Chandra', 'Ketu']
        current_dasha = random.choice(dasha_list)
        return {
            "name": name, "dob_date": dob_date.strftime('%Y-%m-%d'), "ascendant_sign": ascendant_sign, "ascendant_sign_name": ascendant_sign_name,
            "planets": planets_in_house, "mangal_dosha": {"is_present": mangal_dosha_present, "description": "Mangal Dosha present - may affect marriage timing" if mangal_dosha_present else "Mangal Dosha absent - favorable for marriage"},
            "birth_location": pob_text, "coordinates": {"latitude": latitude, "longitude": longitude},
            "timezone": timezone_str, "dasha_periods": {"current_dasha_lord": current_dasha, "current_mahadasha": current_dasha},
            "current_mahadasha": current_dasha, "is_mock_data": True
        }

    def calculate_chart_data(self, name, dob_date, tob_time, pob_text, latitude, longitude, timezone_str):
        """
        Calculates comprehensive chart data using the /kundli/advanced endpoint.
        The most reliable method for generating prediction data.
        """
        access_token = self._get_access_token()
        if not access_token: return self._generate_mock_chart_data(name, dob_date, tob_time, pob_text, latitude, longitude, timezone_str)

        try:
            local_tz = pytz.timezone(timezone_str)
            birth_datetime = datetime.combine(dob_date, tob_time)
            localized_dt = local_tz.localize(birth_datetime)
            api_datetime_str = localized_dt.isoformat()
            if '+' in api_datetime_str and api_datetime_str[-3] != ':': api_datetime_str = api_datetime_str[:-2] + ':' + api_datetime_str[-2:]
            elif api_datetime_str.endswith('+0000'): api_datetime_str = api_datetime_str.replace('+0000', 'Z')
        except Exception as e: logger.error(f"Timezone or Date/Time Error: {e}"); return None

        headers = {"Authorization": f"Bearer {access_token}"}
        base_url = "https://api.prokerala.com/v2/astrology/kundli/advanced" 
        
        common_params = {'ayanamsa': 5, 'coordinates': f"{latitude},{longitude}", 'datetime': api_datetime_str}
        
        kundli_advanced_data = {}
        with requests.Session() as session:
            session.headers.update(headers)
            try:
                response = session.get(base_url, params=common_params, timeout=15)
                response.raise_for_status()
                kundli_advanced_data = response.json().get('data', {})
            except Exception as e:
                logger.error(f"Error fetching Advanced Kundli data: {e}. Falling back to mock.")
                return None
                
        # --- Data Parsing ---
        # NOTE: Using .get() for safe nested dictionary access
        planet_positions = kundli_advanced_data.get('planet_position', {}).get('planet_position', [])
        dasha_periods = kundli_advanced_data.get('dasha', {})
        mangal_dosha = kundli_advanced_data.get('mangal_dosha', {})
        
        planets_in_house = {}
        ascendant_sign = None
        ascendant_sign_name = "N/A"
        planet_code_map = {'Sun': 'Su', 'Moon': 'Mo', 'Mars': 'Ma', 'Mercury': 'Me', 'Jupiter': 'Ju', 'Venus': 'Ve', 'Saturn': 'Sa', 'Rahu': 'Ra', 'Ketu': 'Ke', 'Lagna': 'La'}

        lagna_planet = next((p for p in planet_positions if p.get('id') == 100 or p.get('name') == 'Lagna'), None)
        
        if lagna_planet:
            ascendant_sign = lagna_planet.get('rasi', {}).get('id')
            ascendant_sign_name = lagna_planet.get('rasi', {}).get('name')
            
            if ascendant_sign is not None and ascendant_sign > 0:
                for planet in planet_positions:
                    rasi_id = planet.get('rasi', {}).get('id')
                    planet_name = planet.get('name')
                    
                    if rasi_id is not None and planet_name and rasi_id != 0:
                        house_num = (rasi_id - ascendant_sign + 12) % 12 + 1 
                        planet_code = planet_code_map.get(planet_name, planet_name[:2])
                        
                        house_key = str(house_num)
                        if house_key not in planets_in_house: planets_in_house[house_key] = []
                        if planet_code and planet_code not in planets_in_house[house_key]: planets_in_house[house_key].append(planet_code)
        
        for i in range(1, 13):
            if str(i) not in planets_in_house: planets_in_house[str(i)] = []

        current_mahadasha = dasha_periods.get('mahadasha', {}).get('lord', 'Unknown')
        
        final_chart_data = {
            "name": name, 
            "dob_date": dob_date.strftime('%Y-%m-%d'), 
            "ascendant_sign": ascendant_sign or 1, 
            "ascendant_sign_name": ascendant_sign_name,
            "planets": planets_in_house,
            "birth_location": pob_text, 
            "coordinates": {"latitude": latitude, "longitude": longitude},
            "timezone": timezone_str, 
            "dasha_periods": dasha_periods,
            "current_mahadasha": current_mahadasha,
            "mangal_dosha": {"is_present": mangal_dosha.get('is_present', False), "description": mangal_dosha.get('description', 'Mangal Dosha analysis completed.')},
            "prokerala_data": {"planet_positions": planet_positions}, # Used for Chandra Rashi lookup
            "is_mock_data": False
        }
        return final_chart_data

    def generate_ai_response(self, user_message, chart_data=None):
        """Generates AI response adhering to the strict 5-line format (Rule 1-4, 6, 7)."""
        
        if not OPENAI_API_KEY: return "Authentic answer unavailable: AI key missing. Kripya birth details dein ya baad me try karein."

        if chart_data and chart_data.get('mode') == 'horary':
            return generate_horary_response(chart_data.get('horary_number', 125), user_message, chart_data.get('name', 'User'))

        if not chart_data or chart_data.get('is_mock_data', False):
            if 'horary' in user_message.lower() or 'number' in user_message.lower() or '249' in user_message.lower():
                return "Namaskar, main aapka AstroRemedis ka AI Astrologer hoon.\nAgar aapko birth details nahi pata to 1 se 249 tak koi number soch kar batayein.\nMain us number ke base par KP Horary chart banake aapka analysis karunga.\nKya main aur detail me bataun?\nBhagwan aap par apna aashirwad sadaiv banaaye rakhen."
            else:
                return "Authentic uttar ke liye janm ke vivran (DOB, time, place) avashyak hai. Kripya ye jaankari dein. Bhagwan aap par apna aashirwad sadaiv banaaye rakhen."

        user_name = chart_data.get('name', 'User')
        
        # Identity Facts (Rule 2) - Use planet positions for accurate Moon Rashi
        moon_rashi = next((p.get('rasi', {}).get('name') for p in chart_data.get('prokerala_data', {}).get('planet_positions', []) if p.get('name') == 'Moon'), 'Unknown')
        LAGNA = chart_data.get('ascendant_sign_name', 'Unknown')
        CHANDRA = moon_rashi
        MAHADASH = chart_data.get('current_mahadasha', 'Unknown')
        
        # Dynamic Layers (Rule 3, 4, 6)
        mole_prediction_text = generate_mole_prediction(chart_data)
        lal_kitab = generate_lal_kitab_observation(chart_data)
        
        # RAG Context
        context_from_docs = ""
        if self.vector_store and RAG_AVAILABLE:
            retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})
            relevant_docs = retriever.invoke(user_message)
            raw_docs = "\n\n".join([doc.page_content for doc in relevant_docs])
            context_from_docs = raw_docs[:2000]

        # Chronology Context
        dob_date_str = chart_data.get('dob_date')
        birth_year = datetime.strptime(dob_date_str, '%Y-%m-%d').year if dob_date_str else 2000
        earliest_marriage_year = birth_year + 21
        
        # Build System Prompt for the 5-Line Structure
        system_prompt = f"""
        You are AstroRemedis ka AI Astrologer – a spiritual Pandit Ji and friendly advisor.

        **CRITICAL INSTRUCTIONS (Strict Adherence Required):**
        1. **STRICT 5-LINE FORMAT:** Output EXACTLY 5 lines, separated by newlines. NO LABELS, NO MARKDOWN (except for optional **bolding** for emphasis).
        2. **LINE 1 (GREETING, Fixed):** "Namaskar, main aapka AstroRemedis ka AI Astrologer hoon."
        3. **LINE 5 (BLESSING, Fixed):** "Bhagwan aap par apna aashirwad sadaiv banaaye rakhen."
        4. **LANGUAGE/TONE:** Use 70% Hindi / 30% English mix (Hinglish). Tone must be warm, spiritual, and conversational.
        5. **LINE 2 (KP/Vedic & Guess):** Must state: "Aapki Lagna {LAGNA} hai, Chandra Rashi {CHANDRA} hai, aur iss samay {MAHADASH} Mahadasha chal rahi hai." Then add a Dasha observation AND a human-feel guess (Rule 2).
        6. **LINE 3 (Lal Kitab/Mole/Remedy):** This line must combine Lal Kitab, Mole Prediction, OR a general prediction/remedy based on the chart.
            - **If Lal Kitab exists:** Use its observation + remedy + subtle product mention (Rule 3, 6). E.g., 'Aapke grahon se lagta hai... [remedy].'
            - **If Lal Kitab absent, and Mole asked:** Include the Mole Prediction (Rule 4).
            - **Else:** Give a direct, precise answer to the user's question, integrating the best chart-based remedy/tip.
        7. **LINE 4 (Follow-up):** Must be: "Kya main aur detail me bataun?" (Rule 2)
        8. **CONTENT:** Base all predictions and remedies on the chart data.
        
        **INTERNAL REFERENCE DATA:**
        LAGNA: {LAGNA}, CHANDRA RASHI: {CHANDRA}, MAHADASH: {MAHADASH}
        MOLE PREDICTION: {mole_prediction_text}
        LAL KITAB OBSERVATION: {json.dumps(lal_kitab, ensure_ascii=False) if lal_kitab else "None"}
        RAG CONTEXT: {context_from_docs}
        USER QUESTION: {user_message}
        AGE CHECK: Prediction year must be >= {max(2025, earliest_marriage_year)}.
        """
        
        try:
            response = openai.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": system_prompt}],
                temperature=0.2, 
                max_tokens=260,
                timeout=12
            )
            raw_response = response.choices[0].message.content.strip()
            
            final_response = enforce_identity_consistency(
                raw_response,
                {'lagna': LAGNA, 'chandra_rashi': CHANDRA, 'mahadasha': MAHADASH},
                suppress_identities=False
            )
            return sanitize_ai_text(final_response)
                
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return "Sorry, I encountered a temporary AI capacity issue. Please ask again in a few seconds."

# --- 4. Flask Application Setup ---

app = Flask(__name__)
CORS(app)
astro_api = EnhancedAstroBotAPI()

@app.route('/')
def home():
    return jsonify({"message": "Enhanced AstroBot API is running!", "version": "2.0.0 (Final Logic Integrated)"})

@app.route('/api/health')
def health_check():
    return jsonify({
        "status": "healthy", "timestamp": datetime.now().isoformat(),
        "features": {"rag_enabled": RAG_AVAILABLE and astro_api.vector_store is not None, "openai_enabled": OPENAI_API_KEY is not None, "prokerala_enabled": astro_api.prokerala_enabled}
    })

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        chart_data = data.get('chart_data')
        client_profile = data.get('client_profile') or {}
        
        if not user_message: return jsonify({"error": "Message is required"}), 400
        
        ai_response = astro_api.generate_ai_response(user_message, chart_data)
        
        return jsonify({
            "response": ai_response, "timestamp": datetime.now().isoformat(),
            "user_message": user_message, "rag_enabled": astro_api.vector_store is not None
        })
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/api/kundli', methods=['POST'])
def generate_kundli():
    try:
        data = request.get_json()
        birth_data = parse_birth_data(data)
        latitude, longitude = get_coordinates(birth_data['place'])
        chart_data = astro_api.calculate_chart_data(
            birth_data['name'], birth_data['dob_date'], birth_data['tob_time'],
            birth_data['place'], latitude, longitude, birth_data['timezone']
        )
        if not chart_data: return jsonify({"error": "Failed to generate Kundli. Check API/Credentials."}), 500
        
        moon_rashi = next((p.get('rasi', {}).get('name') for p in chart_data.get('prokerala_data', {}).get('planet_positions', []) if p.get('name') == 'Moon'), 'N/A')
        
        core_facts = {
            'lagna': chart_data.get('ascendant_sign_name'),
            'chandra_rashi': moon_rashi,
            'mahadasha': chart_data.get('current_mahadasha'),
            'mangal_dosha_present': chart_data.get('mangal_dosha', {}).get('is_present', False)
        }
        
        return jsonify({"success": True, "chart_data": chart_data, "core_facts": core_facts})
        
    except ValueError as e: return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error in kundli endpoint: {e}")
        return jsonify({"error": "Failed to generate Kundli", "message": str(e)}), 500

@app.route('/api/kp-horary', methods=['POST'])
def kp_horary_analysis_endpoint():
    try:
        data = request.get_json()
        horary_number = data.get('horary_number')
        question = data.get('question', 'Mere kaam ke baare mein bataiye.')
        user_name = data.get('name', 'User')
        
        if not horary_number: return jsonify({"error": "Horary number is required (1-249)"}), 400
        
        try:
            horary_number = int(horary_number)
            if not (1 <= horary_number <= 249): raise ValueError
        except ValueError: return jsonify({"error": "Horary number must be an integer between 1 and 249"}), 400
        
        ai_response = generate_horary_response(horary_number, question, user_name)
        
        mock_chart_data_for_ai = {'mode': 'horary', 'horary_number': horary_number, 'name': user_name, 'is_mock_data': True}
        
        return jsonify({"success": True, "response": ai_response, "chart_data": mock_chart_data_for_ai})
        
    except Exception as e:
        logger.error(f"Error in KP Horary endpoint: {e}")
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

# Main entry point
if __name__ == '__main__':
    # Google Sheets configuration check
    if GOOGLE_SHEETS_AVAILABLE and not get_env('GOOGLE_SERVICE_ACCOUNT_JSON') and not get_env('GOOGLE_SERVICE_ACCOUNT_FILE'):
        logger.warning("Google Sheets integration disabled - Service Account credentials not found")
        # Ensure append_form_submission is None if the check failed
        append_form_submission = None
        diagnose_connection = None
    
    logger.info("Starting Enhanced AstroBot Backend Server...")
    app.run(debug=True, host='0.0.0.0', port=5000)