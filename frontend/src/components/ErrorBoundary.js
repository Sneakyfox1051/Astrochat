import React from 'react';
import logger from '../utils/logger';

/**
 * ErrorBoundary Component
 * Catches JavaScript errors anywhere in the child component tree,
 * logs those errors, and displays a fallback UI instead of crashing.
 */
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Log error to console for debugging
    logger.error('ErrorBoundary caught an error:', error, errorInfo);
    this.setState({
      error: error,
      errorInfo: errorInfo
    });
    
    // You can also log the error to an error reporting service here
    // e.g., logErrorToService(error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    // Optionally reload the page or reset app state
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      // Custom fallback UI
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.handleReset);
      }

      // Default fallback UI
      return (
        <div style={{
          padding: '20px',
          textAlign: 'center',
          color: '#333',
          backgroundColor: '#f8f9fa',
          borderRadius: '8px',
          margin: '20px'
        }}>
          <h2 style={{ color: '#dc3545', marginBottom: '10px' }}>
            ⚠️ Kuchh galat ho gaya
          </h2>
          <p style={{ marginBottom: '15px' }}>
            Maaf kijiye, kuchh technical issue aa raha hai. Kripya page ko refresh karein ya phir thodi der baad try karein.
          </p>
          {process.env.NODE_ENV === 'development' && this.state.error && (
            <details style={{ 
              marginTop: '15px', 
              textAlign: 'left',
              backgroundColor: '#fff',
              padding: '10px',
              borderRadius: '4px',
              fontSize: '12px'
            }}>
              <summary style={{ cursor: 'pointer', fontWeight: 'bold' }}>
                Technical Details (Development Only)
              </summary>
              <pre style={{ 
                overflow: 'auto', 
                maxHeight: '200px',
                marginTop: '10px'
              }}>
                {this.state.error.toString()}
                {this.state.errorInfo && this.state.errorInfo.componentStack}
              </pre>
            </details>
          )}
          <button
            onClick={this.handleReset}
            style={{
              marginTop: '15px',
              padding: '10px 20px',
              backgroundColor: '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '14px'
            }}
          >
            Phir se try karein
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;





















