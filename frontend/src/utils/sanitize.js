/**
 * Input Sanitization Utility
 * 
 * Provides functions to sanitize user inputs and prevent XSS attacks
 * 
 * Usage:
 *   import { sanitizeInput, sanitizeHTML } from '../utils/sanitize';
 *   const safeInput = sanitizeInput(userInput);
 */

/**
 * Sanitizes text input by removing potentially dangerous characters
 * @param {string} input - User input to sanitize
 * @returns {string} Sanitized input
 */
export const sanitizeInput = (input) => {
  if (typeof input !== 'string') {
    return '';
  }
  
  // Remove HTML tags and script content
  let sanitized = input
    .replace(/<[^>]*>/g, '') // Remove HTML tags
    .replace(/javascript:/gi, '') // Remove javascript: protocol
    .replace(/on\w+\s*=/gi, '') // Remove event handlers
    .trim();
  
  // Limit length to prevent DoS
  if (sanitized.length > 5000) {
    sanitized = sanitized.substring(0, 5000);
  }
  
  return sanitized;
};

/**
 * Sanitizes HTML content (for displaying user-generated content)
 * @param {string} html - HTML string to sanitize
 * @returns {string} Sanitized HTML
 */
export const sanitizeHTML = (html) => {
  if (typeof html !== 'string') {
    return '';
  }
  
  // Create a temporary div to parse HTML
  const div = document.createElement('div');
  div.textContent = html;
  return div.innerHTML;
};

/**
 * Validates phone number format
 * @param {string} phone - Phone number to validate
 * @returns {boolean} True if valid
 */
export const validatePhone = (phone) => {
  if (!phone || typeof phone !== 'string') {
    return false;
  }
  
  // Remove common formatting characters
  const cleaned = phone.replace(/[\s\-()]/g, '');
  
  // Check if it's a valid phone number (10-15 digits)
  const phoneRegex = /^[+]?[0-9]{10,15}$/;
  return phoneRegex.test(cleaned);
};

/**
 * Validates email format
 * @param {string} email - Email to validate
 * @returns {boolean} True if valid
 */
export const validateEmail = (email) => {
  if (!email || typeof email !== 'string') {
    return false;
  }
  
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email.trim());
};

/**
 * Escapes special characters for use in regex
 * @param {string} str - String to escape
 * @returns {string} Escaped string
 */
export const escapeRegex = (str) => {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
};

