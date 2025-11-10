/**
 * FeedbackModal - User Feedback Collection Component
 * 
 * This component displays a modal popup to collect user feedback after the chat session ends.
 * It collects:
 * - User rating (1-5 stars)
 * - Additional feedback/comments
 * 
 * Features:
 * - Modal overlay with backdrop
 * - Star rating system (1-5 stars)
 * - Text area for additional feedback
 * - Submit and skip functionality
 * - Responsive design for mobile and desktop
 * 
 * @component
 * @param {Object} props - Component props
 * @param {boolean} props.isOpen - Whether the modal is open
 * @param {Function} props.onClose - Function to close the modal
 * @param {Function} props.onSubmit - Function to submit the feedback data
 * @returns {JSX.Element} The feedback modal interface
 */

import React, { useState, useEffect } from 'react';
import './FeedbackModal.css';

const FeedbackModal = ({ isOpen, onClose, onSubmit }) => {
  // ===== STATE MANAGEMENT =====
  // Rating state: 0 means no rating selected, 1-5 for star ratings
  const [rating, setRating] = useState(0);
  
  // Hover state for star rating interaction
  const [hoveredRating, setHoveredRating] = useState(0);
  
  // Feedback text state
  const [feedback, setFeedback] = useState('');
  
  // Submission state
  const [isSubmitting, setIsSubmitting] = useState(false);

  // ===== RESET FORM WHEN MODAL OPENS =====
  useEffect(() => {
    if (isOpen) {
      // Reset all form fields when modal opens
      setRating(0);
      setHoveredRating(0);
      setFeedback('');
      setIsSubmitting(false);
      
      // Auto-scroll to top of modal body when it opens
      // This ensures content starts from the beginning
      setTimeout(() => {
        const modalBody = document.querySelector('.feedback-modal-body');
        if (modalBody) {
          modalBody.scrollTop = 0;
        }
      }, 100);
    }
  }, [isOpen]);

  // ===== EVENT HANDLERS =====
  
  /**
   * Handles star rating click
   * @param {number} value - The rating value (1-5)
   */
  const handleRatingClick = (value) => {
    setRating(value);
  };

  /**
   * Handles star hover for visual feedback
   * @param {number} value - The rating value being hovered
   */
  const handleRatingHover = (value) => {
    setHoveredRating(value);
  };

  /**
   * Handles mouse leave from star rating area
   */
  const handleRatingLeave = () => {
    setHoveredRating(0);
  };

  /**
   * Handles feedback text change
   * @param {Event} e - Input change event
   */
  const handleFeedbackChange = (e) => {
    setFeedback(e.target.value);
  };

  /**
   * Handles form submission
   * Validates that at least a rating is provided, then calls onSubmit callback
   */
  const handleSubmit = async () => {
    // Validate that rating is provided
    if (rating === 0) {
      alert('Kripya apna rating select karein (1 se 5 tak stars)');
      return;
    }

    setIsSubmitting(true);

    // Prepare feedback data
    const feedbackData = {
      rating: rating,
      feedback: feedback.trim(),
      timestamp: new Date().toISOString()
    };

    try {
      // Call onSubmit callback with feedback data
      if (onSubmit) {
        await onSubmit(feedbackData);
      }
      
      // Close modal after successful submission
      onClose();
    } catch (error) {
      console.error('Error submitting feedback:', error);
      alert('Feedback submit karne mein koi problem aayi. Kripya dobara try karein.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Don't render if modal is not open
  if (!isOpen) return null;

  return (
    <div className="feedback-modal-overlay" onClick={onClose}>
      <div className="feedback-modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="feedback-modal-header">
          <h2>💬 Aapka Feedback</h2>
          <p>Humare AstroBot ko improve karne mein madad karein</p>
          <button className="feedback-close-btn" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        {/* Modal Body */}
        <div className="feedback-modal-body">
          {/* Rating Section */}
          <div className="feedback-rating-section">
            <label className="feedback-label">
              Aapko hamara service kaisa laga? <span className="required">*</span>
            </label>
            <div className="star-rating-container">
              {[1, 2, 3, 4, 5].map((value) => {
                // Determine if star should be filled
                // Show hovered rating if hovering, otherwise show selected rating
                const isFilled = hoveredRating >= value || (hoveredRating === 0 && rating >= value);
                
                return (
                  <button
                    key={value}
                    type="button"
                    className={`star-button ${isFilled ? 'filled' : ''}`}
                    onClick={() => handleRatingClick(value)}
                    onMouseEnter={() => handleRatingHover(value)}
                    onMouseLeave={handleRatingLeave}
                    aria-label={`Rate ${value} out of 5 stars`}
                  >
                    ★
                  </button>
                );
              })}
            </div>
            {rating > 0 && (
              <p className="rating-text">
                {rating === 1 && '😞 Bahut kharab'}
                {rating === 2 && '😐 Kharab'}
                {rating === 3 && '😊 Theek-thaak'}
                {rating === 4 && '😃 Accha'}
                {rating === 5 && '🤩 Bahut accha!'}
              </p>
            )}
          </div>

          {/* Feedback Text Section */}
          <div className="feedback-text-section">
            <label className="feedback-label" htmlFor="feedback-text">
              Koi aur suggestions ya feedback? (Optional)
            </label>
            <textarea
              id="feedback-text"
              className="feedback-textarea"
              value={feedback}
              onChange={handleFeedbackChange}
              placeholder="Aapka feedback yahan likhein... (e.g., Bot ko aur fast banao, zyada accurate predictions, etc.)"
              rows={5}
              maxLength={500}
            />
            <div className="character-count">
              {feedback.length}/500 characters
            </div>
          </div>

          {/* Contact Section */}
          <div className="feedback-contact-section">
            <p className="contact-text">
              Agar aapko aur guidance chahiye, to hamare professional astrologist se sampark karein:
            </p>
            <a 
              href="https://wa.me/919010356000" 
              target="_blank" 
              rel="noopener noreferrer"
              className="whatsapp-contact-link"
            >
              <span className="whatsapp-icon">💬</span>
              <span className="whatsapp-number">+91 9010356000</span>
            </a>
          </div>
        </div>

        {/* Modal Footer - Outside scrollable body */}
        <div className="feedback-modal-footer">
          <button
            className="feedback-submit-btn"
            onClick={handleSubmit}
            disabled={isSubmitting || rating === 0}
          >
            {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default FeedbackModal;

