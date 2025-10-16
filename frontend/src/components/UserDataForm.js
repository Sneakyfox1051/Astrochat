/**
 * UserDataForm - Modal Form Component for Collecting User Birth Details
 * 
 * This component provides a modal popup form that collects user birth details
 * before entering the chat interface. It replaces the step-by-step data collection
 * in the chat with a single comprehensive form.
 * 
 * Features:
 * - Modal overlay with backdrop
 * - Form validation for all fields
 * - Date and time input handling
 * - Place/city input with suggestions
 * - Submit and cancel functionality
 * - Responsive design for mobile and desktop
 * 
 * @component
 * @param {Object} props - Component props
 * @param {boolean} props.isOpen - Whether the modal is open
 * @param {Function} props.onClose - Function to close the modal
 * @param {Function} props.onSubmit - Function to submit the form data
 * @returns {JSX.Element} The modal form interface
 */

import React, { useState, useEffect } from 'react';
import './UserDataForm.css';
import astroBotAPI from '../services/api';

const UserDataForm = ({ isOpen, onClose, onSubmit }) => {
  const [formData, setFormData] = useState({
    name: '',
    dob: '',
    tob: '',
    place: '',
    timezone: 'Asia/Kolkata'
  });
  
  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setFormData({
        name: '',
        dob: '',
        tob: '',
        place: '',
        timezone: 'Asia/Kolkata'
      });
      setErrors({});
    }
  }, [isOpen]);

  // Handle form input changes
  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    
    // Clear error when user starts typing
    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: ''
      }));
    }
  };

  // Validate form data
  const validateForm = () => {
    const newErrors = {};
    
    // Name validation
    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    } else if (formData.name.trim().length < 2) {
      newErrors.name = 'Name must be at least 2 characters';
    }
    
    // Date of birth validation
    if (!formData.dob) {
      newErrors.dob = 'Date of birth is required';
    } else {
      const dobDate = new Date(formData.dob);
      const today = new Date();
      if (dobDate > today) {
        newErrors.dob = 'Date of birth cannot be in the future';
      } else if (dobDate < new Date('1900-01-01')) {
        newErrors.dob = 'Date of birth cannot be before 1900';
      }
    }
    
    // Time of birth validation
    if (!formData.tob) {
      newErrors.tob = 'Time of birth is required';
    } else {
      const timeRegex = /^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$/;
      if (!timeRegex.test(formData.tob)) {
        newErrors.tob = 'Please enter time in HH:MM format (24-hour)';
      }
    }
    
    // Place validation
    if (!formData.place.trim()) {
      newErrors.place = 'Birth place is required';
    } else if (formData.place.trim().length < 2) {
      newErrors.place = 'Place name must be at least 2 characters';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      // Format the data for the backend
      const formattedData = {
        name: formData.name.trim(),
        dob: formData.dob,
        tob: formData.tob + ':00', // Add seconds
        place: formData.place.trim(),
        timezone: formData.timezone
      };
      
      // Fire-and-forget: submit to backend to store in Google Sheet
      // Do not block UX if Sheets write fails
      astroBotAPI.sendFormData(formattedData).catch(() => {});

      await onSubmit(formattedData);
      onClose();
    } catch (error) {
      console.error('Error submitting form:', error);
      setErrors({ submit: 'Failed to submit form. Please try again.' });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle modal close
  const handleClose = () => {
    if (!isSubmitting) {
      onClose();
    }
  };

  // Handle backdrop click
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      handleClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="user-data-form-overlay" onClick={handleBackdropClick}>
      <div className="user-data-form-modal">
        <div className="form-header">
          <h2>🔮 Kundli Details</h2>
          <p>Please provide your birth details to generate your personalized Kundli chart</p>
          <button 
            className="close-btn" 
            onClick={handleClose}
            disabled={isSubmitting}
          >
            <svg viewBox="0 0 24 24" width="20" height="20">
              <path d="M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              <path d="M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="user-data-form">
          <div className="form-group">
            <label htmlFor="name">Full Name *</label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleInputChange}
              placeholder="Enter your full name"
              className={errors.name ? 'error' : ''}
              disabled={isSubmitting}
            />
            {errors.name && <span className="error-message">{errors.name}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="dob">Date of Birth *</label>
            <input
              type="date"
              id="dob"
              name="dob"
              value={formData.dob}
              onChange={handleInputChange}
              className={errors.dob ? 'error' : ''}
              disabled={isSubmitting}
            />
            {errors.dob && <span className="error-message">{errors.dob}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="tob">Time of Birth *</label>
            <input
              type="time"
              id="tob"
              name="tob"
              value={formData.tob}
              onChange={handleInputChange}
              className={errors.tob ? 'error' : ''}
              disabled={isSubmitting}
            />
            {errors.tob && <span className="error-message">{errors.tob}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="place">Birth Place/City *</label>
            <input
              type="text"
              id="place"
              name="place"
              value={formData.place}
              onChange={handleInputChange}
              placeholder="Enter your birth city"
              className={errors.place ? 'error' : ''}
              disabled={isSubmitting}
            />
            {errors.place && <span className="error-message">{errors.place}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="timezone">Timezone</label>
            <select
              id="timezone"
              name="timezone"
              value={formData.timezone}
              onChange={handleInputChange}
              disabled={isSubmitting}
            >
              <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
              <option value="Asia/Dubai">Asia/Dubai (GST)</option>
              <option value="America/New_York">America/New_York (EST)</option>
              <option value="Europe/London">Europe/London (GMT)</option>
              <option value="Asia/Tokyo">Asia/Tokyo (JST)</option>
            </select>
          </div>

          {errors.submit && (
            <div className="submit-error">
              <span className="error-message">{errors.submit}</span>
            </div>
          )}

          <div className="form-actions">
            <button
              type="button"
              onClick={handleClose}
              className="cancel-btn"
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="submit-btn"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <div className="loading-spinner"></div>
                  Generating Kundli...
                </>
              ) : (
                'Generate Kundli & Start Chat'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default UserDataForm;
