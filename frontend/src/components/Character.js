/**
 * Character Component
 * 
 * Displays the main Astro Pandit character image on the landing page.
 * This is a simple presentational component with no state or props.
 * 
 * @component
 */
import React from 'react';
import './Character.css';

const Character = () => {
  return (
    <div className="character-container">
      <img 
        src={require('../assets/Astro_Client_Final.png')} 
        alt="Astro Pandit" 
        className="character-image" 
      />
    </div>
  );
};

export default Character;


