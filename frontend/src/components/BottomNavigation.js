import React, { useState } from 'react';
import './BottomNavigation.css';

const BottomNavigation = ({ onChatToggle, isChatOpen, onRefreshChat, onShowForm }) => {
  const [isActive, setIsActive] = useState(false);

  // Center (Chat) button: opens the form first; toggles chat if no form handler
  const handleCenterClick = () => {
    setIsActive(!isActive);
    // Show form popup before opening chat
    if (onShowForm) {
      onShowForm();
    } else if (onChatToggle) {
      onChatToggle();
    }
    console.log('Center button clicked - Show form popup');
  };

  // Left close icon: closes chat if open
  const handleCloseClick = () => {
    // Close chat if it's open
    if (isChatOpen && onChatToggle) {
      onChatToggle();
      setIsActive(false);
    }
    console.log('Close button clicked');
  };

  // Right refresh icon: return to main page (leave chat)
  const handleRefreshClick = () => {
    // Close chat if open and navigate to main page
    if (isChatOpen && onChatToggle) {
      onChatToggle();
      setIsActive(false);
    }
    // Navigate to app root (main page). Works in dev and prod builds.
    try {
      window.location.href = window.location.origin + '/';
    } catch (_) {
      // Fallback: hard reload
      window.location.reload();
    }
    console.log('Refresh button clicked - Navigating to main page');
  };

  return (
    <div className="bottom-navigation">
      <div className="nav-row">
        {/* Left Icon - Close/Cross */}
        <div className="nav-icon left-icon" onClick={handleCloseClick}>
        <div className="icon-container">
          <svg viewBox="0 0 24 24" className="close-icon">
            <path d="M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        </div>

        {/* Center Button with Ripple Effect */}
        <div className="nav-center">
        <div className="nav-center-inner">
          <button 
            className={`center-button ${isActive ? 'active' : ''}`}
            onClick={handleCenterClick}
          >
            <div className="ripple-container">
              <div className="ripple ripple-1"></div>
              <div className="ripple ripple-2"></div>
              <div className="ripple ripple-3"></div>
            </div>
            <div className="center-icon">
              {/* Chat bubble icon */}
              <svg viewBox="0 0 24 24" className="chat-icon">
                <path d="M21 12c0 4.418-4.03 8-9 8-1.068 0-2.09-.152-3.04-.433-.313-.095-.641-.143-.969-.143-.445 0-.885.09-1.292.266l-2.32 1.003c-.53.229-1.104-.27-.973-.83l.576-2.46c.087-.37.131-.752.131-1.135 0-.41-.06-.818-.177-1.211C2.34 13.633 2 12.343 2 11c0-4.418 4.03-8 9-8s10 3.582 10 9z" fill="currentColor"/>
                <circle cx="8.5" cy="11.5" r="1" fill="#ffffff"/>
                <circle cx="12" cy="11.5" r="1" fill="#ffffff"/>
                <circle cx="15.5" cy="11.5" r="1" fill="#ffffff"/>
              </svg>
            </div>
          </button>
        </div>
      </div>

        {/* Right Icon - Refresh/Reboot */}
        <div className="nav-icon right-icon" onClick={handleRefreshClick}>
        <div className="icon-container">
          <svg viewBox="0 0 24 24" className="refresh-icon">
            <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M21 3v5h-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M3 21v-5h5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        </div>
      </div>
      <div className="nav-powered-row">
        <div className="powered-by-evoke">
          <span>Powered by </span>
          <a href="https://www.damnart.com/evoke/?gad_source=1&gad_campaignid=22678789359" target="_blank" rel="noreferrer">Evoke AI</a>
        </div>
      </div>
    </div>
  );
};

export default BottomNavigation;
