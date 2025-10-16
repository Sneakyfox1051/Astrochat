/**
 * AstroBotUI - Main Application Component
 * 
 * This is the root component of the AstroRemedis frontend application.
 * It orchestrates all other components and manages the overall application state.
 * 
 * Key Responsibilities:
 * - Chat state management (open/closed)
 * - Form modal state management
 * - User data flow between components
 * - Component communication and event handling
 * - Background layer with animated effects
 * - Responsive layout for desktop and mobile
 * 
 * Component Hierarchy:
 * - AstroBotUI (this component)
 *   ├── Character (3D character display)
 *   ├── ChatBubble (initial chat prompt)
 *   ├── BottomNavigation (chat controls)
 *   ├── ExpandableChat (main chat interface)
 *   └── UserDataForm (birth details modal)
 * 
 * State Management:
 * - isChatOpen: Controls chat window visibility
 * - isFormOpen: Controls form modal visibility
 * - userData: Stores user birth details from form
 * 
 * @component
 * @returns {JSX.Element} The main application interface
 * 
 * @author AstroRemedis Development Team
 * @version 2.0.0
 * @since 2024
 */

import React, { useState } from 'react';
import ChatBubble from './ChatBubble';
import Character from './Character';
import BottomNavigation from './BottomNavigation';
import ExpandableChat from './ExpandableChat';
import UserDataForm from './UserDataForm';
import './AstroBotUI.css';
// No video import; using procedural CSS background for better performance

const AstroBotUI = () => {
  // ===== STATE MANAGEMENT =====
  // Chat interface state - controls main chat window visibility
  const [isChatOpen, setIsChatOpen] = useState(false);
  
  // Form modal state - controls birth details form visibility
  const [isFormOpen, setIsFormOpen] = useState(false);
  
  // User data state - stores birth details from form submission
  const [userData, setUserData] = useState(null);

  // ===== EVENT HANDLERS =====
  
  /**
   * Handles toggling the chat interface between open and closed states.
   * Called when user clicks the chat button in BottomNavigation.
   */
  const handleChatToggle = () => {
    setIsChatOpen(!isChatOpen);
  };

  /**
   * Handles closing the chat interface.
   * Called when user clicks the close button in ExpandableChat.
   */
  const handleCloseChat = () => {
    setIsChatOpen(false);
  };

  /**
   * Handles refreshing the chat by clearing messages and resetting state.
   * Uses custom event dispatch to communicate with ExpandableChat component.
   * Also resets user data to show form again.
   */
  const handleRefreshChat = () => {
    // Trigger refresh event for ExpandableChat
    window.dispatchEvent(new CustomEvent('refreshChat'));
    // Reset user data to show form again
    setUserData(null);
    console.log('Refreshing chat - clearing messages');
  };

  /**
   * Handles showing the user data form popup.
   * Called when user clicks "New Chat" or similar action.
   */
  const handleShowForm = () => {
    setIsFormOpen(true);
  };

  /**
   * Handles closing the user data form popup.
   * Called when user clicks cancel or backdrop.
   */
  const handleCloseForm = () => {
    setIsFormOpen(false);
  };

  /**
   * Handles form submission with user birth data.
   * Stores user data and transitions to chat interface.
   * 
   * @param {Object} data - User birth details from form
   * @param {string} data.name - User's full name
   * @param {string} data.dob - Date of birth (YYYY-MM-DD)
   * @param {string} data.tob - Time of birth (HH:MM:SS)
   * @param {string} data.place - Birth place/city
   * @param {string} data.timezone - Timezone (default: Asia/Kolkata)
   */
  const handleFormSubmit = async (data) => {
    try {
      setUserData(data);        // Store user data for chat
      setIsFormOpen(false);     // Close form modal
      setIsChatOpen(true);      // Open chat interface
      console.log('Form submitted with data:', data);
    } catch (error) {
      console.error('Error handling form submission:', error);
      throw error;
    }
  };

  return (
    <div className="astrobot-container">
      {/* Background layer with animated effects for visual appeal */}
      <div className="background-layer" />

      {/* Top header with application logo */}
      <div className="top-header">
        <img src="/Astro_LOGO.png" alt="AstroBot Logo" className="header-logo" />
      </div>

      {/* Central section containing character and chat bubble when chat is closed */}
      <div className="central-section">
        {!isChatOpen && <Character />}
        {!isChatOpen && <ChatBubble />}
      </div>

      {/* Bottom navigation with chat controls */}
      <BottomNavigation 
        onChatToggle={handleChatToggle} 
        isChatOpen={isChatOpen} 
        onRefreshChat={handleRefreshChat}
        onShowForm={handleShowForm}
      />

      {/* Expandable chat window - shown when chat is open */}
      <ExpandableChat 
        isOpen={isChatOpen} 
        onClose={handleCloseChat} 
        onRefresh={handleRefreshChat}
        userData={userData}
      />

      {/* User Data Form Modal */}
      <UserDataForm
        isOpen={isFormOpen}
        onClose={handleCloseForm}
        onSubmit={handleFormSubmit}
      />
    </div>
  );
};

export default AstroBotUI;
