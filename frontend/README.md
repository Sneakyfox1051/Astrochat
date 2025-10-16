# AstroRemedis Frontend

A modern, responsive React frontend for AstroRemedis astrology chatbot with WhatsApp-style chat interface, form collection, and real-time Kundli chart display.

## 🌟 Features

- **WhatsApp-Style Chat Interface**: User messages on right, bot messages on left
- **Spiritual Pandit Ji Persona**: Warm, empathetic AI responses with 8-10 second delays for predictions
- **Automatic Chart Generation**: Mandatory Kundli chart display after form submission
- **Form Data Collection**: Comprehensive birth details modal with validation
- **Real-time API Integration**: Seamless backend communication
- **Responsive Design**: Mobile-first approach with desktop optimization
- **Service Account Authentication**: Secure Google Sheets integration

## 🚀 Quick Start

### Prerequisites

- Node.js 16+
- npm or yarn
- Running AstroRemedis backend server

### Installation

1. **Navigate to frontend directory**
   ```bash
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Start development server**
   ```bash
   npm start
   ```

The application will open at `http://localhost:3000`

## 📁 Project Structure

```
frontend/
├── public/
│   ├── Astro_LOGO.png          # Application logo
│   └── index.html              # HTML template
├── src/
│   ├── components/             # React components
│   │   ├── AstroBotUI.js       # Main application component
│   │   ├── AstroBotUI.css      # Main application styles
│   │   ├── Character.js         # 3D character display
│   │   ├── Character.css        # Character styles
│   │   ├── ChatBubble.js        # Initial chat prompt
│   │   ├── ChatBubble.css       # Chat bubble styles
│   │   ├── BottomNavigation.js  # Navigation controls
│   │   ├── BottomNavigation.css # Navigation styles
│   │   ├── ExpandableChat.js    # Main chat interface
│   │   ├── ExpandableChat.css   # Chat interface styles
│   │   ├── UserDataForm.js      # Birth details form
│   │   ├── UserDataForm.css     # Form styles
│   │   ├── ChatWindow.js         # Alternative chat window
│   │   ├── ChatWindow.css        # Chat window styles
│   │   ├── KundliChart.js       # Chart display component
│   │   └── KundliChart.css      # Chart styles
│   ├── services/
│   │   └── api.js              # Backend API integration
│   ├── assets/                 # Static assets
│   │   ├── Astro_Avatar.png    # Pandit Ji avatar
│   │   ├── Astro_Client_Final.png # User avatar
│   │   ├── Astro_Backgorund.png   # Background image
│   │   └── Astro_Background.mp4   # Background video
│   ├── index.js               # Application entry point
│   └── index.css              # Global styles
├── package.json              # Dependencies and scripts
└── README.md                 # This file
```

## 🎨 Component Architecture

### Main Components

#### 1. AstroBotUI (Root Component)
- **Purpose**: Main application orchestrator
- **State Management**: Chat visibility, form modal, user data
- **Key Features**: Component coordination, event handling

#### 2. ExpandableChat (Chat Interface)
- **Purpose**: WhatsApp-style chat with Pandit Ji
- **Features**: 
  - 8-10 second delays for predictions
  - Automatic chart generation
  - Spiritual greeting messages
  - Real-time message exchange

#### 3. UserDataForm (Birth Details Modal)
- **Purpose**: Collect user birth information
- **Features**:
  - Form validation
  - Date/time pickers
  - City/place input
  - Timezone selection

#### 4. KundliChart (Chart Display)
- **Purpose**: Display generated Kundli charts
- **Features**: SVG chart rendering, responsive design

### Component Communication Flow

```
UserDataForm → AstroBotUI → ExpandableChat
     ↓              ↓            ↓
Form Data → User State → Chat with Data
     ↓              ↓            ↓
API Submit → Backend → Chart Generation
```

## 🎯 Key Features Implementation

### 1. WhatsApp-Style Chat Interface

**CSS Implementation:**
```css
/* User messages - right side, orange tint */
.message.user .message-bubble {
  background: linear-gradient(135deg, rgba(228, 107, 0, 0.35) 0%, rgba(255, 180, 0, 0.25) 100%);
  border-radius: 12px 12px 2px 12px;
}

/* Bot messages - left side, light gray */
.message-bubble {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.18) 0%, rgba(255, 255, 255, 0.12) 100%);
  border-radius: 12px 12px 12px 2px;
}
```

### 2. Spiritual AI Responses

**Delay Implementation:**
```javascript
// 8-10 second delay for predictions
const looksLikePrediction = /\b(yog|shaadi|career|health|mangal|grah|kundli|prediction|yoga|marriage|job|business|future)\b/i.test(botText || '');
const baseDelay = looksLikePrediction ? 8000 : 1200; // 8s+ for predictions, 1.2s for regular chat
const variableDelay = looksLikePrediction ? Math.min(2000, Math.floor((botText?.length || 0) / 15) * 80) : 500;
const delayMs = baseDelay + variableDelay; // Total 8-10 seconds for predictions
```

### 3. Automatic Chart Generation

**Implementation:**
```javascript
// Auto-generate chart when form is submitted with complete data
const haveAll = (userData.dob && userData.tob && userData.place);
if (haveAll) {
  setCurrentStep('generating');
  generateKundli(); // Automatically generate chart
}
```

### 4. Form Validation

**Validation Rules:**
- Name: Minimum 2 characters
- Date of Birth: Not in future, not before 1900
- Time of Birth: Valid HH:MM format
- Birth Place: Minimum 2 characters
- Timezone: Default Asia/Kolkata

## 🔧 API Integration

### Backend Communication

The frontend communicates with the backend through the `api.js` service:

```javascript
// Example API calls
astroBotAPI.sendChatMessage(message, chartData)
astroBotAPI.generateKundli(birthDetails)
astroBotAPI.generateChart(birthDetails)
astroBotAPI.sendFormData(formData)
```

### API Endpoints Used

| Endpoint | Purpose | Data Flow |
|----------|--------|-----------|
| `/api/chat` | AI chat responses | User message → AI response |
| `/api/kundli` | Generate Kundli data | Birth details → Chart data |
| `/api/chart` | Generate visual chart | Birth details → SVG chart |
| `/api/form-submit` | Store form data | Form data → Google Sheets |

## 🎨 Styling and Design

### Design Principles

1. **Mobile-First**: Responsive design starting from mobile
2. **Glass Morphism**: Translucent backgrounds with blur effects
3. **Spiritual Theme**: Orange/gold color palette
4. **Accessibility**: High contrast, readable fonts

### Color Palette

```css
:root {
  --primary-orange: #E46B00;
  --gold-accent: #FFD54A;
  --background-glass: rgba(255, 255, 255, 0.15);
  --text-primary: #ffffff;
  --text-secondary: rgba(255, 255, 255, 0.7);
}
```

### Responsive Breakpoints

```css
/* Mobile */
@media (max-width: 480px) { ... }

/* Tablet */
@media (min-width: 481px) and (max-width: 768px) { ... }

/* Desktop */
@media (min-width: 769px) { ... }
```

## 🚀 Build and Deployment

### Development

```bash
npm start          # Start development server
npm run build      # Build for production
npm test           # Run tests
npm run eject      # Eject from Create React App
```

### Production Build

```bash
npm run build
```

This creates a `build/` folder with optimized production files.

### Environment Variables

Create `.env` file in frontend directory:

```env
REACT_APP_API_URL=http://localhost:5000
REACT_APP_ENV=development
```

## 🐛 Troubleshooting

### Common Issues

1. **API Connection Failed**
   - Ensure backend server is running on port 5000
   - Check CORS configuration in backend
   - Verify API endpoints are accessible

2. **Chart Not Displaying**
   - Check ProKerala API credentials in backend
   - Verify birth details format
   - Check browser console for errors

3. **Form Validation Errors**
   - Ensure all required fields are filled
   - Check date format (YYYY-MM-DD)
   - Verify time format (HH:MM)

4. **Styling Issues**
   - Clear browser cache
   - Check CSS file imports
   - Verify responsive breakpoints

### Debug Mode

Enable React Developer Tools and check:
- Component state in React DevTools
- Network requests in browser DevTools
- Console errors and warnings

## 📱 Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## 🔒 Security Considerations

- All API calls use HTTPS in production
- No sensitive data stored in localStorage
- Form validation on both client and server
- CORS properly configured

## 📄 License

This project is proprietary software developed for AstroRemedis.

## 🤝 Support

For technical support or questions, contact the AstroRemedis development team.

---

**Version**: 2.0.0  
**Last Updated**: 2024  
**Author**: AstroRemedis Development Team