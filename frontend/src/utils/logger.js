/**
 * Logger Utility
 * 
 * Provides a centralized logging system that:
 * - Only logs in development mode
 * - Always logs errors (even in production)
 * - Can be easily extended for production logging services
 * 
 * Usage:
 *   import logger from '../utils/logger';
 *   logger.log('Debug message');
 *   logger.error('Error message');
 *   logger.warn('Warning message');
 */

const isDevelopment = process.env.NODE_ENV === 'development';

const logger = {
  /**
   * Log debug/info messages (only in development)
   */
  log: (...args) => {
    if (isDevelopment) {
      console.log('[LOG]', ...args);
    }
  },

  /**
   * Log warnings (only in development)
   */
  warn: (...args) => {
    if (isDevelopment) {
      console.warn('[WARN]', ...args);
    }
  },

  /**
   * Log errors (always, even in production)
   * In production, you could send these to an error tracking service
   */
  error: (...args) => {
    console.error('[ERROR]', ...args);
    
    // In production, you could send to error tracking service
    // if (!isDevelopment && window.Sentry) {
    //   window.Sentry.captureException(new Error(args.join(' ')));
    // }
  },

  /**
   * Log API calls (only in development)
   */
  api: (method, url, ...args) => {
    if (isDevelopment) {
      console.log(`[API ${method}]`, url, ...args);
    }
  },

  /**
   * Log performance metrics
   */
  perf: (label, duration) => {
    if (isDevelopment) {
      console.log(`[PERF] ${label}: ${duration.toFixed(2)}ms`);
    }
  }
};

export default logger;








