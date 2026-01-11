/**
 * LocalStorage Utility
 * 
 * Provides safe localStorage operations with error handling
 * and automatic JSON serialization/deserialization
 * 
 * Usage:
 *   import storage from '../utils/storage';
 *   storage.set('key', data);
 *   const data = storage.get('key');
 *   storage.remove('key');
 */

const storage = {
  /**
   * Set item in localStorage
   * @param {string} key - Storage key
   * @param {*} value - Value to store (will be JSON stringified)
   * @returns {boolean} True if successful
   */
  set: (key, value) => {
    try {
      const serialized = JSON.stringify(value);
      localStorage.setItem(key, serialized);
      return true;
    } catch (error) {
      console.error('Error saving to localStorage:', error);
      return false;
    }
  },

  /**
   * Get item from localStorage
   * @param {string} key - Storage key
   * @param {*} defaultValue - Default value if key doesn't exist
   * @returns {*} Parsed value or defaultValue
   */
  get: (key, defaultValue = null) => {
    try {
      const item = localStorage.getItem(key);
      if (item === null) {
        return defaultValue;
      }
      return JSON.parse(item);
    } catch (error) {
      console.error('Error reading from localStorage:', error);
      return defaultValue;
    }
  },

  /**
   * Remove item from localStorage
   * @param {string} key - Storage key
   * @returns {boolean} True if successful
   */
  remove: (key) => {
    try {
      localStorage.removeItem(key);
      return true;
    } catch (error) {
      console.error('Error removing from localStorage:', error);
      return false;
    }
  },

  /**
   * Clear all items from localStorage
   * @returns {boolean} True if successful
   */
  clear: () => {
    try {
      localStorage.clear();
      return true;
    } catch (error) {
      console.error('Error clearing localStorage:', error);
      return false;
    }
  },

  /**
   * Check if localStorage is available
   * @returns {boolean} True if available
   */
  isAvailable: () => {
    try {
      const test = '__storage_test__';
      localStorage.setItem(test, test);
      localStorage.removeItem(test);
      return true;
    } catch {
      return false;
    }
  }
};

export default storage;








