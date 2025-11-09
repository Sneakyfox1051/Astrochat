/**
 * AstroBot API Service
 * Handles all communication with the backend API
 */

// DEPLOYED BACKEND URL - Production (Active for deployment)
const API_BASE_URL_DEPLOYED = 'https://astroremedis.onrender.com';

// LOCAL DEVELOPMENT URL - Commented out for deployment
// const API_BASE_URL_LOCAL = 'http://127.0.0.1:5000';

// Use deployed URL by default, fallback to environment variable if set
const API_BASE_URL = process.env.REACT_APP_API_URL || API_BASE_URL_DEPLOYED;

class AstroBotAPI {
  constructor() {
    this.baseURL = API_BASE_URL;
    console.log('AstroBotAPI initialized with baseURL:', this.baseURL);
  }

  /**
   * Verify backend connectivity
   * @returns {Promise<boolean>} True if backend is accessible
   */
  async verifyConnection() {
    try {
      const response = await fetch(`${this.baseURL}/api/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      return response.ok;
    } catch (error) {
      console.error('Backend connection verification failed:', error);
      console.error('Backend URL:', this.baseURL);
      return false;
    }
  }

  /**
   * Send a chat message to the backend
   * @param {string} message - User message
   * @param {Object} chartData - Optional chart data (for context)
   * @returns {Promise<Object>} API response
   */
  async sendChatMessage(message, chartData = null, clientProfile = null) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 40000);
      const response = await fetch(`${this.baseURL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: message,
          chart_data: chartData,
          client_profile: clientProfile
        }),
        signal: controller.signal
      });
      clearTimeout(timeout);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error sending chat message (attempt 1):', error);
      // Retry once with minimal payload (no chart context) and fresh controller
      try {
        const controller2 = new AbortController();
        const timeout2 = setTimeout(() => controller2.abort(), 40000);
        const response2 = await fetch(`${this.baseURL}/api/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ message }),
          signal: controller2.signal
        });
        clearTimeout(timeout2);
        if (!response2.ok) {
          throw new Error(`HTTP error! status: ${response2.status}`);
        }
        return await response2.json();
      } catch (fallbackError) {
        console.error('Error sending chat message (fallback):', fallbackError);
        throw fallbackError;
      }
    }
  }

  /**
   * Generate Kundli chart
   * @param {Object} birthDetails - Birth details
   * @returns {Promise<Object>} Kundli data
   */
  async generateKundli(birthDetails) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 60000); // Increased timeout to 60s for Kundli generation
      
      const url = `${this.baseURL}/api/kundli`;
      console.log('Generating Kundli - URL:', url);
      console.log('Generating Kundli - Payload:', birthDetails);
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(birthDetails),
        signal: controller.signal
      });
      clearTimeout(timeout);

      if (!response.ok) {
        // Try to include server error details for better debugging
        let serverMessage = '';
        try {
          const errJson = await response.json();
          serverMessage = errJson?.error || errJson?.message || '';
        } catch (_) {
          try { serverMessage = await response.text(); } catch (_) {}
        }
        const detail = serverMessage ? ` - ${serverMessage}` : '';
        throw new Error(`HTTP error! status: ${response.status}${detail}`);
      }

      return await response.json();
    } catch (error) {
      if (error.name === 'AbortError') {
        console.error('Error generating Kundli: Request timeout after 60 seconds');
        throw new Error('Request timeout. Kundli generation is taking longer than expected. Please try again.');
      } else if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError') || error.message.includes('ERR_CONNECTION_RESET')) {
        console.error('Error generating Kundli: Network error - Backend connection was reset');
        console.error('Backend URL:', this.baseURL);
        console.error('This usually means the backend crashed or closed the connection during processing.');
        throw new Error(`Connection reset by backend server. The server may have encountered an error while processing your request. Please check the backend logs and try again.`);
      } else {
        console.error('Error generating Kundli:', error);
        throw error;
      }
    }
  }

  /**
   * Generate visual chart only
   * @param {Object} birthDetails - Birth details
   * @returns {Promise<Object>} Chart data
   */
  async generateChart(birthDetails) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 30000);
      
      const url = `${this.baseURL}/api/chart`;
      console.log('Generating chart - URL:', url);
      console.log('Generating chart - Payload:', birthDetails);
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(birthDetails),
        signal: controller.signal
      });
      clearTimeout(timeout);

      if (!response.ok) {
        let serverMessage = '';
        try {
          const errJson = await response.json();
          serverMessage = errJson?.error || errJson?.message || '';
        } catch (_) {
          try { serverMessage = await response.text(); } catch (_) {}
        }
        const detail = serverMessage ? ` - ${serverMessage}` : '';
        throw new Error(`HTTP error! status: ${response.status}${detail}`);
      }

      return await response.json();
    } catch (error) {
      if (error.name === 'AbortError') {
        console.error('Error generating chart: Request timeout after 30 seconds');
        throw new Error('Request timeout. Please check your connection and try again.');
      } else if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
        console.error('Error generating chart: Network error - Backend may not be running or accessible');
        console.error('Backend URL:', this.baseURL);
        throw new Error(`Cannot connect to backend server at ${this.baseURL}. Please ensure the backend is running.`);
      } else {
        console.error('Error generating chart:', error);
        throw error;
      }
    }
  }

  /**
   * Analyze chart data
   * @param {Object} chartData - Chart data to analyze
   * @returns {Promise<Object>} Analysis result
   */
  async analyzeKundli(chartData) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 20000);
      const response = await fetch(`${this.baseURL}/api/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          chart_data: chartData
        }),
        signal: controller.signal
      });
      clearTimeout(timeout);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error analyzing Kundli:', error);
      throw error;
    }
  }

  /**
   * Send form data to backend to store in Google Sheets
   * @param {Object} formData - {name, dob, tob, place, timezone}
   */
  async sendFormData(formData) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 15000);
      
      const url = `${this.baseURL}/api/form-submit`;
      console.log('Submitting form data - URL:', url);
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
        signal: controller.signal
      });
      clearTimeout(timeout);

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Form submit failed: ${response.status} ${text}`);
      }

      return await response.json();
    } catch (error) {
      if (error.name === 'AbortError') {
        console.error('Error submitting form data: Request timeout');
        return { success: false, error: 'Request timeout. Please check your connection.' };
      } else if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
        console.error('Error submitting form data: Network error - Backend may not be running or accessible');
        console.error('Backend URL:', this.baseURL);
        // Don't throw hard error to avoid blocking UX; return {success:false}
        return { success: false, error: `Cannot connect to backend at ${this.baseURL}. Please ensure the backend is running.` };
      } else {
        console.error('Error submitting form data:', error);
        // Don't throw hard error to avoid blocking UX; return {success:false}
        return { success: false, error: error.message };
      }
    }
  }

  /**
   * Get coordinates for a place
   * @param {string} place - Place name
   * @returns {Promise<Object>} Coordinates data
   */
  async getCoordinates(place) {
    try {
      const response = await fetch(`${this.baseURL}/api/coordinates/${encodeURIComponent(place)}`);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error getting coordinates:', error);
      throw error;
    }
  }

  /**
   * Check if the backend is healthy
   * @returns {Promise<Object>} Health status
   */
  async checkHealth() {
    try {
      const response = await fetch(`${this.baseURL}/api/health`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error checking health:', error);
      throw error;
    }
  }

  /**
   * Generate KP Horary analysis for users without birth details
   * @param {number} horaryNumber - Number between 1-249
   * @returns {Promise<Object>} Horary analysis
   */
  async generateKPHorary(horaryNumber) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 20000);
      const response = await fetch(`${this.baseURL}/api/kp-horary`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          horary_number: horaryNumber
        }),
        signal: controller.signal
      });
      clearTimeout(timeout);

      if (!response.ok) {
        let serverMessage = '';
        try {
          const errJson = await response.json();
          serverMessage = errJson?.error || errJson?.message || '';
        } catch (_) {
          try { serverMessage = await response.text(); } catch (_) {}
        }
        const detail = serverMessage ? ` - ${serverMessage}` : '';
        throw new Error(`HTTP error! status: ${response.status}${detail}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error generating KP Horary:', error);
      throw error;
    }
  }

  /**
   * Generate Lal Kitab environment observation
   * @param {Object} chartData - Chart data for analysis
   * @returns {Promise<Object>} Lal Kitab observation and tips
   */
  async generateLalKitabObservation(chartData) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 20000);
      const response = await fetch(`${this.baseURL}/api/lal-kitab`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          chart_data: chartData
        }),
        signal: controller.signal
      });
      clearTimeout(timeout);

      if (!response.ok) {
        let serverMessage = '';
        try {
          const errJson = await response.json();
          serverMessage = errJson?.error || errJson?.message || '';
        } catch (_) {
          try { serverMessage = await response.text(); } catch (_) {}
        }
        const detail = serverMessage ? ` - ${serverMessage}` : '';
        throw new Error(`HTTP error! status: ${response.status}${detail}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error generating Lal Kitab observation:', error);
      throw error;
    }
  }

  /**
   * Submit form data to Google Sheets
   * @param {Object} formData - Form data object
   * @param {string} formData.name - User's name
   * @param {string} formData.dob - Date of birth (YYYY-MM-DD)
   * @param {string} formData.tob - Time of birth (HH:MM:SS)
   * @param {string} formData.place - Birth place
   * @param {string} formData.timezone - Timezone (default: Asia/Kolkata)
   * @param {string} formData.mode - Mode (kundli or horary)
   * @returns {Promise<Object>} API response
   */
  async submitFormData(formData) {
    try {
      const response = await fetch(`${this.baseURL}/api/form-submit`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: formData.name,
          dob: formData.dob,
          tob: formData.tob,
          place: formData.place,
          timezone: formData.timezone || 'Asia/Kolkata',
          mode: formData.mode || 'kundli'
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error submitting form data:', error);
      throw error;
    }
  }

  /**
   * Submit feedback to Google Sheets
   * @param {Object} feedbackData - Feedback data object
   * @param {number} feedbackData.rating - User rating (1-5)
   * @param {string} feedbackData.feedback - Additional feedback text
   * @param {string} feedbackData.user_name - User's name to link feedback to form (optional)
   * @param {string} feedbackData.timestamp - ISO timestamp (optional)
   * @returns {Promise<Object>} API response
   */
  async submitFeedback(feedbackData) {
    try {
      const response = await fetch(`${this.baseURL}/api/feedback-submit`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          rating: feedbackData.rating,
          feedback: feedbackData.feedback || '',
          user_name: feedbackData.user_name || '',
          timestamp: feedbackData.timestamp || new Date().toISOString()
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Error submitting feedback:', error);
      throw error;
    }
  }
}

// Create and export API instance
const astroBotAPI = new AstroBotAPI();
export default astroBotAPI;
