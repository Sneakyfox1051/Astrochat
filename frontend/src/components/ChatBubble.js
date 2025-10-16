import React from 'react';
import './ChatBubble.css';

const ChatBubble = () => {
  return (
    <div className="chat-bubble-container">
      <div className="chat-bubble">
        <div className="chat-content">
          <span className="chat-text">Namaste 🙏</span>
          <span className="chat-text">AstroRemedis mein aapka swagat hai</span>
        </div>
        <div className="chat-tail"></div>
      </div>
    </div>
  );
};

export default ChatBubble;
