/**
 * AstroBot API Service
 * Handles all communication with the backend API
 */

const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://astroremedis.onrender.com';

class AstroBotAPI {
  constructor() {
    this.baseURL = API_BASE_URL;
  }

  /**
   * Send a chat message to the backend
   * @param {string} message - User message
   * @param {Object} chartData - Optional chart data (for context)
   * @returns {Promise<Object>} API response
   */
  async sendChatMessage(message, chartData = null) {
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
      const timeout = setTimeout(() => controller.abort(), 30000);
      const response = await fetch(`${this.baseURL}/api/kundli`, {
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
      console.error('Error generating Kundli:', error);
      throw error;
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
      const response = await fetch(`${this.baseURL}/api/chart`, {
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
      console.error('Error generating chart:', error);
      throw error;
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
      const response = await fetch(`${this.baseURL}/api/form-submit`, {
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
      console.error('Error submitting form data:', error);
      // Don't throw hard error to avoid blocking UX; return {success:false}
      return { success: false, error: error.message };
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
}

// Create and export API instance
const astroBotAPI = new AstroBotAPI();
export default astroBotAPI;
