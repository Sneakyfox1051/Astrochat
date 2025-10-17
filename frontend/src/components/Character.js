import React from 'react';
import './Character.css';

const Character = () => {
  return (
    <div className="character-container">
      {/* Experimental: Try GIF first, fallback to PNG if GIF fails */}
      <img 
        src={require('../assets/Astro_Client.gif')} 
        alt="Astro Pandit" 
        className="character-image character-gif"
        onError={(e) => {
          // Fallback to PNG if GIF fails to load
          e.target.src = require('../assets/Astro_Client_Final.png');
          e.target.className = 'character-image'; // Remove GIF-specific class on fallback
        }}
      />
    </div>
  );
};

export default Character;


