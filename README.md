# AstroBot - AI-Powered Astrology Chatbot

A sophisticated AI-powered astrology chatbot that combines advanced Kundli generation with intelligent conversational AI. Built with React frontend and Flask backend, featuring RAG (Retrieval Augmented Generation) for context-aware astrology guidance.

## 🚀 Deployment

### Backend (AWS Elastic Beanstalk)

The backend is deployed on AWS Elastic Beanstalk with HTTPS enabled.

**Backend URL**: `https://api.astroremedis.com`

#### Quick Deploy to AWS Elastic Beanstalk

```bash
# Install EB CLI
pip install awsebcli

# Initialize
eb init -p python-3.11 astroremedis

# Create environment
eb create astroremedis-env

# Set environment variables
eb setenv PROKERALA_CLIENT_ID=your_id \
          PROKERALA_CLIENT_SECRET=your_secret \
          OPENAI_API_KEY=your_key \
          OPENAI_ASSISTANT_ID=your_assistant_id

# Deploy
eb deploy
```

### Frontend (Netlify)

The frontend is configured for Netlify deployment with automatic builds.

**Configuration**: See `netlify.toml` for build settings and redirects.

#### Deploy to Netlify

1. Push your code to GitHub/GitLab/Bitbucket
2. Connect your repository to Netlify
3. Netlify will automatically detect the `netlify.toml` configuration
4. The frontend will build and deploy automatically

### Deployment Status
- ✅ Backend deployed on AWS Elastic Beanstalk (HTTPS enabled)
- ✅ Frontend configured for Netlify deployment
- ✅ WSGI entry point configured (wsgi.py)
- ✅ Gunicorn configured for production
- ✅ Environment variables configured

## 🌟 Features

### Frontend
- 🤖 **Interactive Chat Interface** - Modern, responsive chat UI
- 📱 **Mobile-First Design** - Optimized for all devices
- 🎨 **Beautiful Animations** - Smooth transitions and effects
- 💬 **Real-time Messaging** - Instant AI responses
- 🔄 **Message History** - Persistent chat sessions

### Backend
- 🧠 **RAG System** - Retrieval Augmented Generation with KP rules
- 🔮 **Advanced Kundli Generation** - Complete birth chart analysis
- 📊 **Mangal Dosha Calculation** - Comprehensive dosha analysis
- 🌐 **LangChain Integration** - Document processing and knowledge base
- 🤖 **OpenAI GPT-4** - Sophisticated AI responses in Hinglish
- ⏰ **Timezone Support** - Accurate time calculations
- 📍 **Location Services** - Automatic coordinate lookup

## 🏗️ Project Structure

```
astro-main/
├── backend/                 # Flask API Server
│   ├── app.py              # Main Flask application
│   ├── requirements.txt    # Python dependencies
│   └── README.md          # Backend documentation
├── frontend/               # React Frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── services/       # API service layer
│   │   └── assets/        # Images and media
│   ├── package.json       # Node dependencies
│   └── README.md         # Frontend documentation
├── tests/                  # Test Files (Separate from main code)
│   ├── test_assistant_api.py  # OpenAI Assistant API test app
│   ├── requirements.txt    # Test dependencies
│   └── README.md          # Test documentation
├── .ebextensions/          # AWS Elastic Beanstalk configuration
├── docs/                  # Knowledge Base Documents
│   ├── KP_RULE_1.docx    # KP Astrology Rules
│   ├── KP_RULE_2.docx    # KP Astrology Rules
│   └── KP_RULE_3.docx    # KP Astrology Rules
└── README.md             # This file
```

## 🚀 Quick Start

### Prerequisites
- **Node.js** (v14 or higher)
- **Python** (v3.8 or higher)
- **ProKerala API** account (for Kundli generation)
- **OpenAI API** key (for AI responses)

### 1. Backend Setup

```bash
# Navigate to backend directory
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Configure environment variables
cp env_example.txt .env
# Edit .env with your API credentials:
# - PROKERALA_CLIENT_ID
# - PROKERALA_CLIENT_SECRET
# - OPENAI_API_KEY

# Start the backend server
python start_server.py
```

The backend will be available at `http://localhost:5000`

### 2. Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install Node.js dependencies
npm install

# Start the frontend development server
npm start
```

The frontend will be available at `http://localhost:3000`

## 🔧 Configuration

### Required API Keys

1. **ProKerala API** (Required for Kundli generation)
   - Visit [ProKerala API](https://api.prokerala.com/)
   - Sign up and get your Client ID and Secret
   - Add to `.env` file

2. **OpenAI API** (Required for RAG and AI responses)
   - Visit [OpenAI Platform](https://platform.openai.com/)
   - Get your API key
   - Add to `.env` file

### Environment Variables

Create a `.env` file in the backend directory:

```env
# ProKerala API Credentials (Required)
PROKERALA_CLIENT_ID=your_client_id_here
PROKERALA_CLIENT_SECRET=your_client_secret_here

# OpenAI API Key (Required for RAG)
OPENAI_API_KEY=your_openai_api_key_here

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True
```

## 📦 Project Structure

```
astro-main/
├── wsgi.py                # WSGI entry point for AWS
├── application.py         # Alternative entry point
├── Procfile              # Gunicorn configuration
├── requirements.txt      # Python dependencies
├── .ebextensions/        # AWS Elastic Beanstalk configs
├── backend/              # Flask API Server
│   ├── app.py           # Main Flask application
│   ├── config.py        # Configuration
│   └── google_sheets.py # Google Sheets integration
├── frontend/            # React Frontend
│   ├── build/           # Production build
│   ├── src/             # Source code
│   └── package.json     # Node dependencies
└── docs/                # Knowledge Base Documents
```

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API information and features |
| GET | `/api/health` | Health check with feature status |
| POST | `/api/chat` | Send chat messages and get AI responses |
| POST | `/api/kundli` | Generate comprehensive Kundli chart |
| POST | `/api/analyze` | Analyze Kundli data using RAG |

### Example API Usage

#### Chat Message
```javascript
const response = await fetch('http://localhost:5000/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: 'Tell me about my marriage prospects',
    chart_data: chartData // Optional: for context-aware responses
  })
});
```

#### Generate Kundli
```javascript
const response = await fetch('http://localhost:5000/api/kundli', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    name: 'John Doe',
    dob: '1990-05-15',
    tob: '14:30:00',
    place: 'Delhi, India',
    timezone: 'Asia/Kolkata'
  })
});
```

## 🧪 Testing

### Backend Testing
```bash
cd backend
python app.py
```


### Manual Testing
1. Start both backend and frontend servers
2. Open `http://localhost:3000` in browser
3. Test chat functionality
4. Test Kundli generation (requires API credentials)

## 🔮 Advanced Features

### RAG (Retrieval Augmented Generation)
- Loads KP astrology rules from Word documents
- Creates vector embeddings using OpenAI
- Provides context-aware responses based on chart data
- Maintains respectful Hinglish conversation style

### Mangal Dosha Analysis
- Calculates Mangal Dosha presence
- Provides detailed descriptions
- Integrates with overall chart analysis

### Timezone Handling
- Supports all major timezones
- Accurate birth time calculations
- Proper datetime localization

## 🛠️ Development

### Backend Development
```bash
cd backend
export FLASK_DEBUG=True
python app.py
```

### Frontend Development
```bash
cd frontend
npm start
```

### Adding New Features
1. Backend: Add new endpoints in `app.py`
2. Frontend: Create new components in `src/components/`
3. API: Update service layer in `src/services/api.js`

## 📊 Performance

- **RAG Response Time**: ~2-3 seconds
- **Kundli Generation**: ~1-2 seconds
- **Basic Chat**: ~0.5 seconds
- **Frontend Load Time**: <2 seconds

## 🔒 Security

- Environment variables for sensitive data
- CORS configuration for frontend communication
- Input validation and sanitization
- Error handling without exposing internals

## 🐛 Troubleshooting

### Common Issues

1. **CORS Errors**
   - Ensure Flask-CORS is installed
   - Check CORS configuration

2. **API Credentials**
   - Verify ProKerala credentials
   - Check OpenAI API key validity

3. **Document Loading**
   - Ensure `docs/` folder contains Word files
   - Check file permissions

4. **Port Conflicts**
   - Change ports in configuration if needed
   - Update frontend API URL accordingly

### Debug Mode
```bash
# Backend debug
export FLASK_DEBUG=True
python app.py

# Frontend debug
npm start
```

## 📈 Roadmap

- [ ] WebSocket support for real-time chat
- [ ] User authentication and profiles
- [ ] Chart visualization improvements
- [ ] Multi-language support
- [ ] Mobile app development
- [ ] Advanced prediction algorithms

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- **ProKerala API** for astrology calculations
- **OpenAI** for AI capabilities
- **LangChain** for document processing
- **React** and **Flask** communities

---

**Built with ❤️ for the astrology community**