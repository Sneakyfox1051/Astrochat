import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import './ExpandableChat.css';
import astroBotAPI from '../services/api';
import KundliChart from './KundliChart';
import FeedbackModal from './FeedbackModal';
import logger from '../utils/logger';
import { sanitizeInput } from '../utils/sanitize';
import storage from '../utils/storage';

/**
 * ExpandableChat
 * End-to-end chat flow including:
 * - Greeting and stepwise data capture (fallback if form not used)
 * - Sequential Kundli -> Chart generation (guarded, one-time per session)
 * - Chart rendered as a compact chat card within messages
 * - AI chat responses with Kundli context
 */
const ExpandableChat = ({ isOpen, onClose, onRefresh, userData }) => {
  // Chat state and user profile data captured from form or stepwise prompts
  // Try to restore messages from localStorage, otherwise use default greeting
  const getInitialMessages = () => {
    try {
      const savedMessages = storage.get('chat_messages', null);
      if (savedMessages && Array.isArray(savedMessages) && savedMessages.length > 0) {
        // Only restore if messages are recent (within last 24 hours)
        const lastMessage = savedMessages[savedMessages.length - 1];
        if (lastMessage && lastMessage.timestamp) {
          // Restore messages
          return savedMessages;
        }
      }
    } catch (e) {
      logger.warn('Failed to restore messages from localStorage:', e);
    }
    // Default greeting messages
    return [
      {
        id: 1,
        text: "Jai Shri Ram 🙏 Swagat hai aapka AstroRemedis par. Main aapka AstroRemedis ka AI Astrologer hoon. Aap kaise hain?",
        sender: 'pandit',
        timestamp: new Date().toLocaleTimeString()
      },
      {
        id: 2,
        text: "Aapka naam kya hai aur kis vishay par margdarshan chahte hain? Pehle apna naam batayiye (e.g., Mera naam Rajesh hai).",
        sender: 'pandit',
        timestamp: new Date().toLocaleTimeString()
      }
    ];
  };
  
  const [messages, setMessages] = useState(getInitialMessages);
  const [inputText, setInputText] = useState('');
  const [userProfile, setUserProfile] = useState({
    name: '',
    dob: '',
    tob: '',
    place: '',
    timezone: 'Asia/Kolkata'
  });
  const [kundliData, setKundliData] = useState(null);
  const [chartData, setChartData] = useState(null);
  const [isGeneratingKundli, setIsGeneratingKundli] = useState(false);
  const [isGeneratingChart, setIsGeneratingChart] = useState(false);
  const [isLoadingFadingOut, setIsLoadingFadingOut] = useState(false);
  // Steps: ask_name, ask_dob, ask_tob, ask_place, confirm_details, generating, chart_generated, chatting
  const [currentStep, setCurrentStep] = useState('ask_name');
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const [editMode, setEditMode] = useState(false);
  const messageIdRef = useRef(3);
  const [isBotTyping, setIsBotTyping] = useState(false);
  // Ensure chart is generated only once per chat session
  const timeoutRefs = useRef([]); // Track all timeouts for cleanup
  
  // ===== THREAD MANAGEMENT =====
  // Store thread_id for conversation continuity (prevents backend resets)
  const [threadId, setThreadId] = useState(null);

  // ===== CHAT TIMER STATE =====
  // Timer for chat session limit
  // 5 minutes (300 seconds) for chat session
  const [timeRemaining, setTimeRemaining] = useState(300);
  const timerIntervalRef = useRef(null); // Reference to the countdown interval
  const [timerExpired, setTimerExpired] = useState(false);
  const [showPayButton, setShowPayButton] = useState(false);

  // ===== FEEDBACK MODAL STATE =====
  // Controls visibility of the feedback modal
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);

  // Session profile to keep identities consistent and avoid repetition after first reply
  const [sessionProfile, setSessionProfile] = useState({
    lagna: null,
    chandra_rashi: null,
    mahadasha: null,
    introduced_core_facts: false
  });

  // Cap verbose AI replies and keep only the first 3–5 bullets
  const limitAndCleanResponse = useCallback((text) => {
    if (!text) return '';
    let cleaned = String(text).replace(/\s+$/,'').replace(/^\s+/,'');
    const lines = cleaned.split('\n');

    // Identify remedy block lines we must always keep
    const mustKeepIdx = new Set();
    for (let i = 0; i < lines.length; i++) {
      const ln = lines[i];
      if (/^\s*1\.\s+/.test(ln)) mustKeepIdx.add(i);
      if (/^\s*2\.\s+/.test(ln)) mustKeepIdx.add(i);
      if (/^\s*Activation:\s*/i.test(ln)) mustKeepIdx.add(i);
      if (/^\s*Main aapko sirf trusted AstroRemedis remedies suggest/i.test(ln)) mustKeepIdx.add(i);
    }

    let bulletCount = 0;
    const kept = [];
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const isBullet = /^\s*(?:[-•\u2022]|\d+\.)\s+/.test(line);
      if (isBullet && !mustKeepIdx.has(i)) {
        bulletCount += 1;
        if (bulletCount > 5) continue;
      }
      kept.push(line);
    }

    cleaned = kept.join('\n');
    // Soft cap overall length for UI, but try to preserve remedy block by increasing budget slightly
    const words = cleaned.split(/\s+/);
    const wordLimit = 160; // was 130
    if (words.length > wordLimit) {
      cleaned = words.slice(0, wordLimit).join(' ') + '…';
    }
    return cleaned;
  }, []);
  const hasGeneratedRef = useRef(false);
  const generationTimerRef = useRef(null);

  // Cleanup all timeouts on unmount
  useEffect(() => {
    return () => {
      // Clear all tracked timeouts
      timeoutRefs.current.forEach(timeoutId => clearTimeout(timeoutId));
      timeoutRefs.current = [];
      // Clear generation timer
      if (generationTimerRef.current) {
        clearTimeout(generationTimerRef.current);
        generationTimerRef.current = null;
      }
      // Clear chat timer interval
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
        timerIntervalRef.current = null;
      }
    };
  }, []);

  /**
   * Generate unique message IDs to prevent React key conflicts.
   * Uses timestamp + counter to ensure uniqueness even in rapid succession.
   * 
   * @returns {string} Unique message ID (e.g., "1730891234567_3")
   */
  const nextMessageId = () => {
    const id = `${Date.now()}_${messageIdRef.current}`;
    messageIdRef.current += 1;
    return id;
  };

  // ===== CHAT TIMER LOGIC =====
  /**
   * Timer Effect - Manages the 3-minute chat session timer
   * 
   * Behavior:
   * - Starts countdown when chat opens (isOpen = true)
   * - Resets to 30 seconds when chat opens (for testing - change to 180 for production)
   * - Decrements every second
   * - When timer reaches 0:
   *   1. Shows a farewell message to the user
   *   2. Automatically closes the chat after 2 seconds
   * - Cleans up interval when chat closes or component unmounts
   */
  useEffect(() => {
    if (isOpen) {
      // Reset timer to 5 minutes (300 seconds) when chat opens
      setTimeRemaining(300);
      // Reset timer expired and pay button states
      setTimerExpired(false);
      setShowPayButton(false);
      
      // Start countdown timer - updates every second
      timerIntervalRef.current = setInterval(() => {
        setTimeRemaining(prev => {
          // When timer reaches 0 or below, end the chat session
          if (prev <= 1) {
            // Clear the interval to stop the countdown
            clearInterval(timerIntervalRef.current);
            timerIntervalRef.current = null;
            
            // Set timer expired state and show pay button
            setTimerExpired(true);
            setShowPayButton(true);
            
            // Add a farewell message to inform the user
            setMessages(prev => [...prev, {
              id: nextMessageId(),
              text: "⏰ Aapka session khatam ho gaya hai. Dhanyawad! Aap dobara chat kar sakte hain.",
              sender: 'pandit',
              timestamp: new Date().toLocaleTimeString()
            }]);
            
            // Show feedback modal after a brief delay (2 seconds) to let user read the message
            const feedbackTimer = setTimeout(() => {
              setShowFeedbackModal(true);
            }, 2000);
            timeoutRefs.current.push(feedbackTimer);
            
            return 0; // Set to 0 to prevent negative values
          }
          // Decrement timer by 1 second
          return prev - 1;
        });
      }, 1000); // Update every 1000ms (1 second)
    } else {
      // When chat closes, clear the timer interval
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
        timerIntervalRef.current = null;
      }
    }

    // Cleanup function - runs when component unmounts or dependencies change
    return () => {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
        timerIntervalRef.current = null;
      }
    };
  }, [isOpen, onClose]);

  // When userData is provided (from the modal form), greet the user by name and prefill profile
  useEffect(() => {
    if (userData && userData.name) {
      // Clear any previous chart on a new session start
      setChartData(null);
      setKundliData(null);
      setUserProfile(prev => ({
        ...prev,
        name: userData.name,
        dob: userData.dob || prev.dob,
        tob: userData.tob || prev.tob,
        place: userData.place || prev.place,
        timezone: userData.timezone || prev.timezone,
        mode: userData.mode || 'kundli'
      }));

      // Check if it's horary mode
      if (userData.mode === 'horary') {
        // Horary mode greeting
        setMessages([
          {
            id: 1,
            text: "Aapne KP Horary analysis choose kiya hai. Ye ek powerful method hai jo birth details ke bina bhi accurate predictions deta hai.",
            sender: 'pandit',
            timestamp: new Date().toLocaleTimeString()
          },
          {
            id: 2,
            text: "Agar aapko birth details nahi pata to 1 se 249 tak koi number soch kar batayein. Main us number ke base par aapka analysis karunga.",
            sender: 'pandit',
            timestamp: new Date().toLocaleTimeString()
          }
        ]);
        setCurrentStep('horary_waiting');
      } else {
        // Regular Kundli mode greeting
        setMessages([
          {
            id: 1,
            text: `Jai Shri Ram 🙏 ${userData.name} ji, swagat hai aapka AstroRemedis par. Main aapka AstroRemedis ka AI Astrologer hoon. Aap kaise hain?`,
            sender: 'pandit',
            timestamp: new Date().toLocaleTimeString()
          },
          {
            id: 2,
            text: "Main abhi aapka Kundli chart taiyar kar raha hun... Kripya thoda wait karein, grahon ki sthiti dekhni hai.",
            sender: 'pandit',
            timestamp: new Date().toLocaleTimeString()
          }
        ]);

        const haveAll = (userData.dob && userData.tob && userData.place);
        if (haveAll) {
          // Auto-generate chart when all details are available
          if (!hasGeneratedRef.current) {
            setCurrentStep('generating');
            const details = {
              name: userData.name,
              dob: userData.dob,
              tob: userData.tob,
              place: userData.place,
              timezone: userData.timezone || 'Asia/Kolkata'
            };
            // Mark as generating immediately to avoid duplicate triggers in Strict Mode
            hasGeneratedRef.current = true;
            if (generationTimerRef.current) clearTimeout(generationTimerRef.current);
            const timerId = setTimeout(() => {
              generateKundli(details);
            }, 150);
            generationTimerRef.current = timerId;
            timeoutRefs.current.push(timerId);
          }
        } else {
          setCurrentStep('ask_dob');
        }
      }
    }
  }, [userData]);

  // Handle refresh - clear messages and reset to initial state
  useEffect(() => {
    if (onRefresh) {
      const resetMessages = () => {
        // Reset the message ID counter to avoid collisions after refresh
        messageIdRef.current = 3;
        setMessages([
          {
            id: 1,
            text: "Jai Shri Ram 🙏 Swagat hai aapka AstroRemedis par. Main aapka AstroRemedis ka AI Astrologer hoon. Aap kaise hain?",
            sender: 'pandit',
            timestamp: new Date().toLocaleTimeString()
          },
          {
            id: 2,
            text: "Aapka naam kya hai aur kis vishay par margdarshan chahte hain? Pehle apna naam batayiye (e.g., Mera naam Rajesh hai).",
            sender: 'pandit',
            timestamp: new Date().toLocaleTimeString()
          }
        ]);
        setInputText('');
        setUserProfile({
          name: '',
          dob: '',
          tob: '',
          place: '',
          timezone: 'Asia/Kolkata'
        });
        setKundliData(null);
        setChartData(null);
        if (generationTimerRef.current) {
          clearTimeout(generationTimerRef.current);
          generationTimerRef.current = null;
        }
        hasGeneratedRef.current = false;
        setCurrentStep('ask_name');
        setEditMode(false);
        // Reset thread_id on refresh to start new conversation
        setThreadId(null);
      };
      
      // Listen for refresh events
      const handleRefresh = () => {
        resetMessages();
        // Reset timer to 5 minutes (300 seconds)
        setTimeRemaining(300);
        // Clear any existing timer interval
        if (timerIntervalRef.current) {
          clearInterval(timerIntervalRef.current);
          timerIntervalRef.current = null;
        }
        // Reset timer expired and pay button states
        setTimerExpired(false);
        setShowPayButton(false);
        // Close feedback modal if open
        setShowFeedbackModal(false);
      };
      
      // Store the handler so we can clean it up
      window.addEventListener('refreshChat', handleRefresh);
      
      return () => {
        window.removeEventListener('refreshChat', handleRefresh);
      };
    }
  }, [onRefresh]);

  // Auto-scroll to latest message
  useEffect(() => {
    try {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    } catch (e) {
      // ignore scroll errors
    }
    // Initialize session profile from chart context once available
    const ctx = kundliData || chartData;
    if (ctx && !(sessionProfile.lagna || sessionProfile.chandra_rashi || sessionProfile.mahadasha)) {
      const lagna = ctx.lagna || ctx.ascendant || null;
      const chandra = ctx.chandra_rashi || ctx.moon_sign || null;
      const dasha = ctx.current_mahadasha || ctx.mahadasha || null;
      if (lagna || chandra || dasha) {
        setSessionProfile((p) => ({ ...p, lagna, chandra_rashi: chandra, mahadasha: dasha }));
      }
    }
  }, [messages, isGeneratingKundli, isGeneratingChart, chartData]);

  // Auto-save messages to localStorage whenever they change
  useEffect(() => {
    if (messages.length > 0) {
      try {
        storage.set('chat_messages', messages);
      } catch (e) {
        logger.warn('Failed to auto-save messages:', e);
      }
    }
  }, [messages]);

  // Auto-focus input when chat opens or bot finished typing
  useEffect(() => {
    if (isOpen && !isBotTyping && !isGeneratingKundli) {
      try { inputRef.current?.focus(); } catch (e) {}
    }
  }, [isOpen, isBotTyping, isGeneratingKundli]);

  // NLP helpers for stepwise extraction
  const parseName = (text) => {
    const input = text.trim();
    const cleanup = (raw) => {
      if (!raw) return null;
      // Remove trailing Hindi copula words like 'hai', 'hun', 'hu'
      let name = raw.replace(/\b(hai|hun|hu|hoon)\b\.?$/i, '').trim();
      // Remove trailing punctuation
      name = name.replace(/[.,;:!?]+$/g, '').trim();
      // Collapse multiple spaces
      name = name.replace(/\s{2,}/g, ' ');
      return name || null;
    };

    // 1) "mera naam <name> hai" (common Hindi pattern)
    let m = input.match(/(?:^|\b)mera\s+naam\s+([a-zA-Z][a-zA-Z\s'.-]*?)(?:\s+(?:hai|hun|hu|hoon))?\b/i);
    if (m) return cleanup(m[1]);

    // 2) "my name is <name>"
    m = input.match(/(?:^|\b)my\s+name\s+is\s+([a-zA-Z][a-zA-Z\s'.-]+)$/i);
    if (m) return cleanup(m[1]);

    // 3) "I am <name>" or "I'm <name>"
    m = input.match(/^(?:i\s*am|i'm)\s+([a-zA-Z][a-zA-Z\s'.-]+)$/i);
    if (m) return cleanup(m[1]);

    // 4) Bare name fallback (single or multi-word letters only)
    m = input.match(/^([a-zA-Z][a-zA-Z\s'.-]{1,})$/);
    if (m) return cleanup(m[1]);

    return null;
  };

  const parseDob = (text) => {
    const monthNames = ['january','february','march','april','may','june','july','august','september','october','november','december'];
    const monthShort = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'];
    let m;
    m = text.match(/(\d{4})[\/\-\.](\d{1,2})[\/\-\.](\d{1,2})/); // YYYY-MM-DD
    if (m) return `${m[1]}-${m[2].padStart(2,'0')}-${m[3].padStart(2,'0')}`;
    m = text.match(/(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})/); // DD-MM-YYYY or MM-DD-YYYY
    if (m) {
      const a = parseInt(m[1],10), b = parseInt(m[2],10);
      // Heuristic: if both <=12, assume DD-MM-YYYY by default
      const day = a; const month = b;
      return `${m[3]}-${month.toString().padStart(2,'0')}-${day.toString().padStart(2,'0')}`;
    }
    m = text.match(/(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{4})/i);
    if (m) {
      const month = monthNames.indexOf(m[2].toLowerCase()) !== -1 
        ? monthNames.indexOf(m[2].toLowerCase()) + 1
        : monthShort.indexOf(m[2].toLowerCase()) + 1;
      return `${m[3]}-${month.toString().padStart(2,'0')}-${m[1].padStart(2,'0')}`;
    }
    return null;
  };

  const parseTob = (text) => {
    let m = text.match(/(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(am|pm)?/i);
    if (!m) m = text.match(/(\d{1,2})[\.\s](\d{2})\s*(am|pm)?/i);
    if (m) {
      let hour = parseInt(m[1],10);
      const minute = m[2];
      const sec = m[3] || '00';
      const period = (m[4] || m[3]) || '';
      if (/pm/i.test(period) && hour !== 12) hour += 12;
      if (/am/i.test(period) && hour === 12) hour = 0;
      if (hour >= 0 && hour <= 23) return `${hour.toString().padStart(2,'0')}:${minute}:${sec}`;
    }
    return null;
  };

  const parsePlace = (text) => {
    const m = text.match(/(?:place|sthan|city|town|birth\s*place|janm\s*sthan|from|in)\s*:?\s*([a-zA-Z][a-zA-Z\s,.'-]+)/i);
    if (m) return m[1].trim();
    // Fallback: single word or two words capitalized
    const m2 = text.match(/^[a-zA-Z][a-zA-Z\s'.-]{2,}$/);
    if (m2) return m2[0].trim();
    return null;
  };

  const parseHoraryNumber = (text) => {
    // Extract number from text
    const m = text.match(/(\d+)/);
    if (m) {
      const num = parseInt(m[1], 10);
      if (num >= 1 && num <= 249) {
        return num;
      }
    }
    return null;
  };


  const isValidDate = (yyyyMmDd) => {
    if (!yyyyMmDd) return false;
    const m = yyyyMmDd.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return false;
    const d = new Date(`${m[1]}-${m[2]}-${m[3]}T00:00:00Z`);
    return !isNaN(d.getTime());
  };

  const isValidTime = (hhmmss) => /^(\d{2}):(\d{2}):(\d{2})$/.test(hhmmss);

  // Helper function to check if all birth details are collected
  const isProfileComplete = () => {
    return userProfile.name && userProfile.dob && userProfile.tob && userProfile.place;
  };

  // Helper function to generate Kundli and then Chart (sequential flow)
  // Accepts optional details to avoid relying on possibly stale state
  const generateKundli = async (detailsOverride) => {
    // if guard is already set and a generation is in-flight or done, skip
    if (hasGeneratedRef.current && (isGeneratingKundli || chartData || kundliData)) return;
    setIsGeneratingKundli(true);
    setIsGeneratingChart(true);
    setCurrentStep('generating');
    // Minimum delay before showing chart (reduced to 2 seconds)
    const minDelayMs = 2000;
    const genStartTs = Date.now();
    
    try {
      const birthDetails = detailsOverride || {
        name: userProfile.name,
        dob: userProfile.dob,
        tob: userProfile.tob,
        place: userProfile.place,
        timezone: userProfile.timezone
      };
      // CHART FIRST: Generate and show visual chart as fast as possible
      const chartResponse = await astroBotAPI.generateChart(birthDetails);
      const chartPayload = chartResponse && chartResponse.chart_data ? chartResponse.chart_data : null;
      if (chartResponse.success && chartPayload) {
        setChartData(chartPayload);
        setCurrentStep('chart_generated');
        hasGeneratedRef.current = true;

        // Push chart into the chat timeline so it scrolls up with new messages (only once)
        setMessages(prev => {
          const alreadyHasChart = prev.some(m => m.type === 'chart');
          if (alreadyHasChart) return prev;
          return [...prev, {
            id: nextMessageId(),
            sender: 'pandit',
            type: 'chart',
            chartData: chartPayload,
            timestamp: new Date().toLocaleTimeString()
          }];
        });
        // Note: isGeneratingChart will be set to false when chart is actually rendered (via onChartReady callback)
      } else {
        throw new Error(chartResponse.error || 'Chart generation failed');
      }

      // Then, in background, fetch Kundli JSON (advanced) and store for chat
      try {
        const kundliResponse = await astroBotAPI.generateKundli(birthDetails);
        if (kundliResponse.success && kundliResponse.chart_data) {
          setKundliData(kundliResponse.chart_data);
        }
      } catch (e) {
        logger.error('Background Kundli fetch failed:', e);
      }
    } catch (error) {
      logger.error('Error generating Kundli:', error);
      
      // Preserve user profile data - don't clear it on error
      // The userProfile state is already preserved, we just need to make sure it's not cleared
      
      // Create error message with retry option
      const errorMessage = {
        id: nextMessageId(),
        text: `Sorry, Kundli generate karne mein connection problem aa rahi hai. Aapka data save hai - kripya "Retry" button par click karein.`,
        sender: 'pandit',
        timestamp: new Date().toLocaleTimeString(),
        hasError: true,
        errorType: 'kundli_generation',
        // Store birth details for retry
        retryData: detailsOverride || {
          name: userProfile.name,
          dob: userProfile.dob,
          tob: userProfile.tob,
          place: userProfile.place,
          timezone: userProfile.timezone
        }
      };
      setMessages(prev => [...prev, errorMessage]);
      
      // Reset generation flags so user can retry
      // User profile data is preserved in userProfile state - no need to clear it
      setIsGeneratingKundli(false);
      setIsGeneratingChart(false);
      hasGeneratedRef.current = false; // Allow retry
      // Don't change currentStep - keep user at their current position
      // They can retry using the retry button without losing their place
    } finally {
      setIsGeneratingKundli(false);
    }
  };

  // Generate horary-specific responses for follow-up questions
  const generateHoraryResponse = async (question, userProfile) => {
    try {
      // Create a horary-specific context for the AI
      const horaryContext = {
        mode: 'horary',
        name: userProfile.name,
        question: question,
        analysis_type: 'KP Horary Analysis'
      };

      // Send to backend with horary context and thread_id for conversation continuity
      const response = await astroBotAPI.sendChatMessage(question, horaryContext, null, threadId);
      // Update thread_id from response if provided
      if (response.thread_id) {
        setThreadId(response.thread_id);
      }
      return response.response;
    } catch (error) {
      logger.error('Error generating horary response:', error);
      return "Horary analysis mein koi problem aayi hai. Kripya question dobara puchh sakte hain.";
    }
  };

  /**
   * handleSendMessage - Main message handler that processes user input
   * 
   * Flow:
   * 1. Adds user message to chat
   * 2. Shows typing indicator
   * 3. Routes based on currentStep:
   *    - horary_waiting: Validates 1-249 number, calls KP Horary API
   *    - ask_name/tob/dob/place: Stepwise data collection
   *    - confirm_details: Validates and triggers Kundli generation
   *    - chatting: Sends to backend /api/chat with chart_data context
   * 4. Handles errors gracefully with user-friendly messages
   */
  const handleSendMessage = async () => {
    if (inputText.trim()) {
      // Sanitize user input before sending
      const sanitizedText = sanitizeInput(inputText.trim());
      if (!sanitizedText) {
        // If sanitization removed everything, don't send
        return;
      }
      
      const newMessage = {
        id: nextMessageId(),
        text: sanitizedText,
        sender: 'user',
        timestamp: new Date().toLocaleTimeString()
      };
      
      setMessages([...messages, newMessage]);
      const currentInput = sanitizedText;
      setInputText('');
      
      // Save messages to localStorage for persistence
      try {
        storage.set('chat_messages', [...messages, newMessage]);
      } catch (e) {
        logger.warn('Failed to save messages to localStorage:', e);
      }
      
      try {
        // Show typing indicator
        const typingMessage = {
          id: nextMessageId(),
          text: "",
          sender: 'pandit',
          timestamp: new Date().toLocaleTimeString(),
          isTyping: true
        };
        setIsBotTyping(true);
        setMessages(prev => [...prev, typingMessage]);
        
        // Stepwise dialog
        let botText = '';
        if (currentStep === 'horary_waiting') {
          // Handle horary number input
          const horaryNumber = parseHoraryNumber(currentInput);
          if (!horaryNumber) {
            botText = "Kripya 1 se 249 tak koi number batayiye. Ye number aapke question ke liye cosmic timing determine karega.";
          } else {
            // Route horary analysis via /api/chat with horary context
            try {
              const reply = await generateHoraryResponse(`Horary number: ${horaryNumber}`, userProfile);
              botText = reply;
              setCurrentStep('chatting');
            } catch (error) {
              logger.error('Horary analysis error:', error);
              botText = "Horary analysis mein koi problem aayi hai. Kripya ek aur number try karein.";
            }
          }
        } else if (currentStep === 'ask_name') {
          // allow corrections like: name: Rajesh
          let name = null;
          const correction = currentInput.match(/^(?:name|naam)\s*[:\-]\s*(.+)$/i);
          if (correction) name = correction[1].trim();
          if (!name) name = parseName(currentInput);
          if (!name) {
            botText = "Kripya apna naam clear tarike se batayiye (e.g., Mera naam Anil hai).";
          } else {
            const updated = { ...userProfile, name };
            setUserProfile(updated);
            setCurrentStep('ask_dob');
            botText = `${name} ji, ab apni janm tithi batayiye (e.g., 15/05/1990 ya 15 May 1990).`;
          }
        } else if (currentStep === 'ask_dob') {
          const dob = parseDob(currentInput);
          if (!dob || !isValidDate(dob)) {
            botText = "Janm tithi samajh nahi aayi. Kripya format mein batayein: DD/MM/YYYY ya 15 May 1990.";
          } else {
            const updated = { ...userProfile, dob };
            setUserProfile(updated);
            setCurrentStep('ask_tob');
            botText = "Shukriya. Ab apna janm samay batayiye (e.g., 2:30 PM ya 14:30).";
          }
        } else if (currentStep === 'ask_tob') {
          const tob = parseTob(currentInput);
          if (!tob || !isValidTime(tob)) {
            botText = "Janm samay samajh nahi aaya. Kripya format mein batayein: HH:MM AM/PM ya 24-hour (e.g., 14:30).";
          } else {
            const updated = { ...userProfile, tob };
            setUserProfile(updated);
            setCurrentStep('ask_place');
            botText = "Samay mil gaya. Ab apna janm sthan/city batayiye (e.g., Delhi, Mumbai).";
          }
        } else if (currentStep === 'ask_place') {
          const place = parsePlace(currentInput);
          if (!place) {
            botText = "Janm sthan samajh nahi aaya. Kripya city ka naam batayein (e.g., Pune).";
          } else {
            const updated = { ...userProfile, place };
            setUserProfile(updated);
            setCurrentStep('confirm_details');
            botText = `Kripya confirm karein:\n- Naam: ${updated.name}\n- DOB: ${updated.dob}\n- TOB: ${updated.tob}\n- Place: ${updated.place}\nType karein: 'yes' ya jis field ko change karna ho: 'change name: <naya naam>'`;
          }
        } else if (currentStep === 'confirm_details') {
          if (/^y(es)?$/i.test(currentInput.trim())) {
            botText = "Bahut badiya! Main aapka Kundli chart generate kar raha hun...";
            setCurrentStep('generating');
            // proceed without removing typing bubble
        setMessages(prev => prev.filter(msg => !msg.isTyping).concat({
          id: nextMessageId(),
              text: botText,
              sender: 'pandit',
              timestamp: new Date().toLocaleTimeString()
            }));
            if (hasGeneratedRef.current) return; // already scheduled/generated
            const details = {
              name: userProfile.name,
              dob: userProfile.dob,
              tob: userProfile.tob,
              place: userProfile.place,
              timezone: userProfile.timezone
            };
            // Small buffer to ensure any last state changes settle
            hasGeneratedRef.current = true;
            await new Promise(res => {
              const id = setTimeout(res, 150);
              timeoutRefs.current.push(id);
            });
            await generateKundli(details);
            return;
          }
          const change = currentInput.match(/^change\s+(name|naam|dob|date|tob|time|samay|place|city|sthan)\s*[:\-]\s*(.+)$/i);
          if (change) {
            const field = change[1].toLowerCase();
            const value = change[2].trim();
            const updated = { ...userProfile };
            if (field === 'name' || field === 'naam') updated.name = value;
            else if (field === 'dob' || field === 'date') {
              const dob = parseDob(value);
              if (dob && isValidDate(dob)) updated.dob = dob; else {
                botText = "Nayi DOB valid nahi hai. Example: 15/05/1990";
              }
            } else if (field === 'tob' || field === 'time' || field === 'samay') {
              const tob = parseTob(value);
              if (tob && isValidTime(tob)) updated.tob = tob; else {
                botText = "Naya TOB valid nahi hai. Example: 2:30 PM ya 14:30";
              }
            } else if (field === 'place' || field === 'city' || field === 'sthan') {
              const place = parsePlace(value);
              if (place) updated.place = place; else {
                botText = "Naya place samajh nahi aaya. Example: Jaipur";
              }
            }
            setUserProfile(updated);
            if (!botText) {
              botText = `Updated. Kripya confirm karein:\n- Naam: ${updated.name}\n- DOB: ${updated.dob}\n- TOB: ${updated.tob}\n- Place: ${updated.place}\nType 'yes' ya 'change <field>: <value>'`;
            }
          } else {
            botText = "Kripya 'yes' type karein ya 'change <field>: <value>' batayein (e.g., change dob: 1990-05-15).";
          }
        } else if (currentStep === 'chart_generated' || currentStep === 'chatting') {
          // Check if we're in horary mode
          if (userProfile.mode === 'horary') {
            // For horary mode, provide complete answers based on horary analysis
            botText = await generateHoraryResponse(currentInput, userProfile);
          } else {
          // Regular chat with chart context; prefer Kundli data (has name and rich context)
          const chartContext = kundliData || chartData || null;
          const response = await astroBotAPI.sendChatMessage(
            currentInput,
            chartContext,
            {
              lagna: sessionProfile.lagna,
              chandra_rashi: sessionProfile.chandra_rashi,
              mahadasha: sessionProfile.mahadasha,
              introduced_core_facts: sessionProfile.introduced_core_facts
            },
            threadId // Pass thread_id for conversation continuity
          );
            botText = response.response;
            // Update thread_id from response if provided
            if (response.thread_id) {
              setThreadId(response.thread_id);
            }
          }
          setCurrentStep('chatting');

          // After first bot reply, capture identities if present and mark introduced to suppress repeats later
          if (!sessionProfile.introduced_core_facts) {
            const textSample = botText || '';
            const lagnaMatch = textSample.match(/(?:Lagna|Ascendant)\s+([A-Za-z]+)/i);
            const chMatch = textSample.match(/(?:Chandra\s*Rashi|Moon\s*sign|Moonsign)\s+([A-Za-z]+)/i);
            const mdMatch = textSample.match(/(?:Mahadasha|Maha\s*Dasha|Current\s*Dasha)\s+([A-Za-z]+)/i);
            setSessionProfile((p) => ({
              lagna: p.lagna || (lagnaMatch ? lagnaMatch[1] : null),
              chandra_rashi: p.chandra_rashi || (chMatch ? chMatch[1] : null),
              mahadasha: p.mahadasha || (mdMatch ? mdMatch[1] : null),
              introduced_core_facts: true
            }));
          }
        } else if (currentStep === 'generating') {
          botText = "Chart generate ho raha hai, kripya wait karein...";
        }

        // Remove initial typing indicator immediately
        setMessages(prev => prev.filter(msg => !msg.isTyping));
        
        // Clean and cap response
        const capped = limitAndCleanResponse(botText || '');
        
        // Split response into chunks by paragraphs (aim for 3 messages)
        const splitIntoParagraphs = (text) => {
          if (!text) return [];
          
          // Split by double newlines first (paragraph breaks)
          let paragraphs = text.split(/\n\s*\n+/).filter(p => p.trim().length > 0);
          
          // If no double newlines, try splitting by single newlines
          if (paragraphs.length === 1) {
            paragraphs = text.split(/\n+/).filter(p => p.trim().length > 0);
          }
          
          // If still only one paragraph, try intelligent splitting by sentences
          if (paragraphs.length === 1 && text.length > 150) {
            // Split by sentence endings (period, exclamation, question mark) followed by space
            const sentences = text.split(/(?<=[.!?])\s+/).filter(s => s.trim().length > 0);
            
            if (sentences.length > 1) {
              // Group sentences into ~3 chunks (aim for 3 messages)
              const targetChunks = 3;
              const chunkSize = Math.ceil(sentences.length / targetChunks);
              paragraphs = [];
              for (let i = 0; i < sentences.length; i += chunkSize) {
                const chunk = sentences.slice(i, i + chunkSize).join(' ').trim();
                if (chunk) paragraphs.push(chunk);
              }
            }
          }
          
          // Ensure we have at least 1 and at most 3 chunks
          if (paragraphs.length === 0) {
            paragraphs = [text];
          } else if (paragraphs.length > 3) {
            // Merge excess paragraphs into the last one
            const lastParagraph = paragraphs.slice(2).join('\n\n');
            paragraphs = [...paragraphs.slice(0, 2), lastParagraph];
          } else if (paragraphs.length === 1 && text.length > 300) {
            // Force split long single paragraph into 3 roughly equal parts
            const thirdLength = Math.ceil(text.length / 3);
            const firstBreak = text.lastIndexOf('.', thirdLength);
            const secondBreak = text.lastIndexOf('.', thirdLength * 2);
            
            if (firstBreak > 0 && secondBreak > firstBreak) {
              paragraphs = [
                text.substring(0, firstBreak + 1).trim(),
                text.substring(firstBreak + 1, secondBreak + 1).trim(),
                text.substring(secondBreak + 1).trim()
              ];
            }
          }
          
          return paragraphs.filter(p => p.trim().length > 0);
        };
        
        const parts = splitIntoParagraphs(capped);
        
        const sendChunk = async (idx) => {
          if (idx >= parts.length) return;
          
          // Show typing indicator for 1-2 seconds before each chunk (randomized for natural feel)
          const typingDelay = 1000 + Math.random() * 1000; // 1s to 2s
          const typingMsg = {
            id: nextMessageId(),
            text: '',
            sender: 'pandit',
            timestamp: new Date().toLocaleTimeString(),
            isTyping: true
          };
          setMessages(prev => ([...prev, typingMsg]));
          await new Promise(r => {
            const id = setTimeout(r, typingDelay);
            timeoutRefs.current.push(id);
          });
          
          // Replace typing bubble with actual chunk
          setMessages(prev => {
            const withoutTyping = prev.filter(m => !m.isTyping);
            return [...withoutTyping, {
              id: nextMessageId(), // Use nextMessageId to ensure unique IDs
              text: parts[idx].trim(),
              sender: 'pandit',
              timestamp: new Date().toLocaleTimeString()
            }];
          });
          
          // Continue with next chunk (with a small delay between messages)
          await new Promise(r => {
            const id = setTimeout(r, 300); // 300ms gap between messages
            timeoutRefs.current.push(id);
          });
          await sendChunk(idx + 1);
        };
        
        await sendChunk(0);
        // Backend now handles follow-up questions, so no need for separate frontend follow-up
        setIsBotTyping(false);
        
      } catch (error) {
        logger.error('Error sending message:', error);
        
        // Remove typing indicator and show error
        setMessages(prev => {
          const withoutTyping = prev.filter(msg => !msg.isTyping);
          const errorResponse = {
            id: nextMessageId(),
            text: "Sorry, main abhi online nahi hun. Kripya thoda baad try karein.",
            sender: 'pandit',
            timestamp: new Date().toLocaleTimeString()
          };
          return [...withoutTyping, errorResponse];
        });
        setIsBotTyping(false);
      }
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSendMessage();
    }
  };

  // ===== TIMER HELPER FUNCTION =====
  /**
   * Formats seconds into MM:SS format for display
   * 
   * @param {number} seconds - Total seconds remaining
   * @returns {string} Formatted time string (e.g., "03:00", "02:45", "00:30")
   * 
   * Example:
   * - formatTime(180) => "03:00"
   * - formatTime(45) => "00:45"
   * - formatTime(0) => "00:00"
   */
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // ===== FEEDBACK HANDLERS =====
  /**
   * Handles feedback modal close
   * Closes the feedback modal and then closes the chat
   */
  const handleFeedbackClose = () => {
    setShowFeedbackModal(false);
    // Close chat after feedback modal is closed
    if (onClose) {
      setTimeout(() => {
        onClose();
      }, 300); // Small delay for smooth transition
    }
  };

  /**
   * Handles feedback submission
   * Logs feedback data and can be extended to send to backend API
   * 
   * @param {Object} feedbackData - Feedback data object
   * @param {number} feedbackData.rating - User rating (1-5)
   * @param {string} feedbackData.feedback - Additional feedback text
   * @param {string} feedbackData.timestamp - ISO timestamp
   */
  const handleFeedbackSubmit = async (feedbackData) => {
    try {
      // Get user name from userData or userProfile to link feedback to form submission
      const userName = userData?.name || userProfile?.name || '';
      
      // Add user name to feedback data so it can be linked to the form submission
      const feedbackWithUser = {
        ...feedbackData,
        user_name: userName
      };
      
      // Send feedback to backend API (which saves to Google Sheets)
      await astroBotAPI.submitFeedback(feedbackWithUser);
      
      logger.log('Feedback submitted successfully to Google Sheets!');
      
      // Close feedback modal and chat
      setShowFeedbackModal(false);
      if (onClose) {
        setTimeout(() => {
          onClose();
        }, 300);
      }
    } catch (error) {
      logger.error('Error submitting feedback:', error);
      throw error; // Re-throw to let modal handle the error
    }
  };

  if (!isOpen) return null;

  return (
    <div className={`expandable-chat-container ${isOpen ? 'expanded' : ''}`}>
      {/* ===== TIMER WIDGET - CORNER DISPLAY =====
          Displays the countdown timer in the top-right corner
          - Shows remaining time in MM:SS format
          - Changes to warning style (red) when <= 30 seconds remain
          - Only visible when chat is open
      */}
      {isOpen && (
        <div className={`chat-timer-widget ${timeRemaining <= 30 ? 'warning' : ''}`}>
          <div className="timer-icon">⏱️</div>
          <div className="timer-text">{formatTime(timeRemaining)}</div>
        </div>
      )}

      {/* Chat Header */}
      <div className="chat-header">
        <div className="pandit-info">
          <div className="pandit-avatar-small">
            <img src={require('../assets/Astro_Client_Final.png')} alt="Pandit ji" />
          </div>
          <div className="pandit-details">
            <h3>Pandit ji</h3>
            <span className="status">Online</span>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="messages-container">
        {messages.map((message) => (
          message.type === 'chart' ? (
            <div key={message.id} className={`message pandit chart-card`}>
              <div className="message-avatar">
                <img src={require('../assets/Astro_Client_Final.png')} alt="Pandit ji" />
              </div>
              <div className="message-content" style={{maxWidth: '100%'}}>
                <div className="message-bubble">
                  <KundliChart
                    chartData={message.chartData}
                    compact
                    onChartReady={() => {
                      // Chart is now visible on screen - fade out loading then stop
                      setIsLoadingFadingOut(true);
                      setTimeout(() => {
                        setIsGeneratingChart(false);
                        setIsGeneratingKundli(false);
                        setIsLoadingFadingOut(false);
                      }, 500); // Match CSS transition duration
                    }}
                  />
                  <span className="message-time">{message.timestamp}</span>
                </div>
              </div>
            </div>
          ) : (
            <div key={message.id} className={`message ${message.sender}`}>
              {message.sender === 'pandit' && (
                <div className="message-avatar">
                  <img src={require('../assets/Astro_Client_Final.png')} alt="Pandit ji" />
                </div>
              )}
              <div className="message-content">
                <div className={`message-bubble ${message.isTyping ? 'typing' : ''} ${message.hasError ? 'error-message' : ''}`}>
                  {message.isTyping ? (
                    <div className="typing-dots" aria-label="Pandit ji typing">
                      <span></span><span></span><span></span>
                    </div>
                  ) : (
                    <>
                      <p>{message.text}</p>
                      {message.hasError && message.retryData && (
                        <button 
                          className="retry-button"
                          onClick={() => {
                            // Retry Kundli generation with stored data
                            generateKundli(message.retryData);
                            // Remove the error message from the list
                            setMessages(prev => prev.filter(m => m.id !== message.id));
                          }}
                          disabled={isGeneratingKundli}
                        >
                          {isGeneratingKundli ? '⏳ Retrying...' : '🔄 Retry'}
                        </button>
                      )}
                    </>
                  )}
                  <span className="message-time">{message.timestamp}</span>
                </div>
              </div>
            </div>
          )
        ))}
        <div ref={messagesEndRef} />
        
        {/* Chart is now part of messages only; no separate rendering here */}
        
        {/* Loading indicator for Kundli generation */}
        {(isGeneratingKundli || isGeneratingChart) && (
          <div className={`kundli-loading ${isLoadingFadingOut ? 'fade-out' : ''}`}>
            <div className="loading-content">
              <div className="loading-spinner-enhanced">
                <div className="spinner-ring"></div>
                <div className="spinner-ring"></div>
                <div className="spinner-ring"></div>
                <div className="spinner-center">🔮</div>
              </div>
              <div className="loading-text">
                <p className="loading-title">Aapka Kundli chart generate ho raha hai...</p>
                <div className="loading-steps">
                  <span className="step active">📊 Planetary positions calculate kar rahe hain</span>
                  <span className="step">🌟 Chart rendering...</span>
                  <span className="step">✨ Almost ready!</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="input-container">
        <div className="input-wrapper">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyPress={handleKeyPress}
            ref={inputRef}
            placeholder={
              currentStep === 'greeting' || currentStep === 'collecting_details'
                ? "Format: naam, DD/MM/YYYY, HH:MM, place (e.g., Rajesh, 15/05/1990, 14:30, Delhi)"
                : "Apna sawal yahan likhein..."
            }
            className="message-input"
            disabled={isGeneratingKundli || isBotTyping}
            aria-label="Type your message"
            aria-describedby="input-help-text"
            maxLength={5000}
          />
          <span id="input-help-text" className="sr-only">
            Type your question and press Enter or click Send button
          </span>
          <button 
            onClick={handleSendMessage} 
            className="send-button"
            disabled={isGeneratingKundli || isBotTyping}
            aria-label="Send message"
            aria-disabled={isGeneratingKundli || isBotTyping}
            type="button"
          >
            <svg viewBox="0 0 24 24" className="send-icon">
              <path d="M22 2L11 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
          {/* Removed Edit details button per request */}
        </div>
      </div>

      {/* ===== FEEDBACK MODAL =====
          Shows feedback popup when timer expires
          Collects user rating and additional feedback
      */}
      <FeedbackModal
        isOpen={showFeedbackModal}
        onClose={handleFeedbackClose}
        onSubmit={handleFeedbackSubmit}
      />
    </div>
  );
};

// Memoize component to prevent unnecessary re-renders
export default React.memo(ExpandableChat);
