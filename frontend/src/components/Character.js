import React from 'react';
import './Character.css';

const Character = () => {
  return (
    <div className="character-container">
      <img src={require('../assets/Astro_Client_Final.png')} alt="Astro Pandit" className="character-image" />
    </div>
  );
};

export default Character;


