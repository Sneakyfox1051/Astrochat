import React, { useState } from 'react';
import './ExpandableChat.css';
import astroBotAPI from '../services/api';
import KundliChart from './KundliChart';

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
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: "Jai Shri Ram 🙏 Swagat hai aapka AstroRemedis par. Main aapka digital Pandit Ji hoon.",
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
  // Steps: ask_name, ask_dob, ask_tob, ask_place, confirm_details, generating, chart_generated, chatting
  const [currentStep, setCurrentStep] = useState('ask_name');
  const messagesEndRef = React.useRef(null);
  const inputRef = React.useRef(null);
  const [editMode, setEditMode] = useState(false);
  const messageIdRef = React.useRef(3);
  const [isBotTyping, setIsBotTyping] = useState(false);
  // Ensure chart is generated only once per chat session
  const hasGeneratedRef = React.useRef(false);
  const generationTimerRef = React.useRef(null);

  // When userData is provided (from the modal form), greet the user by name and prefill profile
  React.useEffect(() => {
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
        timezone: userData.timezone || prev.timezone
      }));

      // Personalized spiritual greeting
      setMessages([
        {
          id: 1,
          text: `Jai Shri Ram 🙏 ${userData.name} ji, swagat hai aapka AstroRemedis par. Main aapka digital Pandit Ji hoon. Aap kaise hain?`,
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
          generationTimerRef.current = setTimeout(() => {
            generateKundli(details);
          }, 150);
        }
      } else {
        setCurrentStep('ask_dob');
      }
    }
  }, [userData]);

  const nextMessageId = () => {
    const id = messageIdRef.current;
    messageIdRef.current += 1;
    return id;
  };

  // Handle refresh - clear messages and reset to initial state
  React.useEffect(() => {
    if (onRefresh) {
      const resetMessages = () => {
        setMessages([
          {
            id: 1,
            text: "Jai Shri Ram 🙏 Swagat hai aapka AstroRemedis par. Main aapka digital Pandit Ji hoon.",
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
      };
      
      // Listen for refresh events
      const handleRefresh = () => {
        resetMessages();
      };
      
      // Store the handler so we can clean it up
      window.addEventListener('refreshChat', handleRefresh);
      
      return () => {
        window.removeEventListener('refreshChat', handleRefresh);
      };
    }
  }, [onRefresh]);

  // Auto-scroll to latest message
  React.useEffect(() => {
    try {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    } catch (e) {
      // ignore scroll errors
    }
  }, [messages, isGeneratingKundli, isGeneratingChart, chartData]);

  // Auto-focus input when chat opens or bot finished typing
  React.useEffect(() => {
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

  // Pick relevant follow-up prompts based on the latest user intent
  const selectFollowUps = (userText, context = {}) => {
    const text = (userText || '').toLowerCase();
    const topics = [];
    const push = (arr) => arr[Math.floor(Math.random() * arr.length)];

    const sets = {
      marriage: [
        'Aapke shaadi ke yog ke baare mein aur detail chahiye?',
        'Kya rishta ki baat chal rahi hai filhaal?',
        'Shaadi timeline ke baare mein specific sawal puchna chahenge?'
      ],
      career: [
        'Aap kaam kis field mein karte hain?',
        'Job change ya promotion ka soch rahe hain?',
        'Business/Startup ko lekar koi specific sawal hai?'
      ],
      health: [
        'Health ke kaunse area ko lekar chinta hai?',
        'Lifestyle/discipline ke baare mein guidance chahiye?',
        'Koi chronic issue hai jiske upchar chahte hain?'
      ],
      finance: [
        'Investment ko lekar aapka plan kya hai?',
        'Savings ya expenses control par sawal hai?',
        'Business finance ya income growth par guidance chahiye?'
      ],
      education: [
        'Kaunse course/field par vichar kar rahe hain?',
        'Higher studies ya certification ka plan hai?',
        'Study location India ya Abroad par guidance chahiye?'
      ],
      travel: [
        'Aap short-term travel chahte hain ya relocation?',
        'Work-related travel ya personal yatra?',
        'Kab ke aas-paas travel plan kar rahe hain?'
      ],
      property: [
        'Ghar kharidne ya bechne ka plan hai?',
        'Loan/EMI suitability par sawal hai?',
        'Kis city/area mein property dekh rahe hain?'
      ],
      children: [
        'Family planning ke baare mein koi specific date range chahte hain?',
        'Bacchon ki education ya health par guidance chahiye?',
        'Parenting support ya vastu tips chahiye?'
      ],
      generic: [
        'Kis vishay par next focus chahte hain — marriage, career, health, finance?',
        'Kya aap current dasha/antardasha ke impact par discuss karna chahenge?',
        'Aapko remedies (mantra, daan, gemstone) par specific guidance chahiye?'
      ]
    };

    if (/shaadi|marriage|partner|relationship|manglik|mangal/i.test(text)) topics.push('marriage');
    if (/career|job|business|work|profession|promotion|startup/i.test(text)) topics.push('career');
    if (/health|illness|hospital|fitness|diet|stress/i.test(text)) topics.push('health');
    if (/money|finance|income|wealth|investment|loan|emi|property/i.test(text)) topics.push('finance');
    if (/study|education|college|exam|course|degree/i.test(text)) topics.push('education');
    if (/travel|visa|abroad|relocate|yatra/i.test(text)) topics.push('travel');
    if (/property|house|home|flat|land|plot/i.test(text)) topics.push('property');
    if (/child|children|baby|pregnan/i.test(text)) topics.push('children');

    // If no clear topic, pick based on recent context
    if (!topics.length) {
      if (context.lastTopic) topics.push(context.lastTopic);
    }
    if (!topics.length) topics.push('generic');

    const primary = topics[0];
    return push(sets[primary] || sets.generic);
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
    // Ensure the experience feels Antral: minimum 8-10s before showing chart
    const minDelayMs = 8000 + Math.floor(Math.random() * 2000);
    const genStartTs = Date.now();
    
    try {
      const birthDetails = detailsOverride || {
        name: userProfile.name,
        dob: userProfile.dob,
        tob: userProfile.tob,
        place: userProfile.place,
        timezone: userProfile.timezone
      };
      // 1) Generate Kundli first
      const kundliResponse = await astroBotAPI.generateKundli(birthDetails);

      if (!kundliResponse.success || !kundliResponse.chart_data) {
        throw new Error(kundliResponse.error || 'Kundli generation failed');
      }

      setKundliData(kundliResponse.chart_data);

      // Add Kundli generation success message with warm greeting and remedy promise
      const successMessage = {
        id: nextMessageId(),
        text: `🎉 Bahut badhiya ${userProfile.name} ji! Aapka Kundli taiyar ho gaya hai. Ab main visual chart generate kar raha hun...`,
        sender: 'pandit',
        timestamp: new Date().toLocaleTimeString()
      };
      setMessages(prev => [...prev, successMessage]);

      // 2) Only after Kundli succeeds, generate Chart
      const chartResponse = await astroBotAPI.generateChart(birthDetails);
      if (chartResponse.success && chartResponse.chart_data) {
        // Wait for remaining time to meet minimum delay
        const elapsed = Date.now() - genStartTs;
        const remaining = Math.max(0, minDelayMs - elapsed);
        if (remaining > 0) {
          await new Promise(res => setTimeout(res, remaining));
        }
        setChartData(chartResponse.chart_data);
        setIsGeneratingChart(false);
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
            chartData: chartResponse.chart_data,
            timestamp: new Date().toLocaleTimeString()
          }];
        });
      } else {
        throw new Error(chartResponse.error || 'Chart generation failed');
      }
    } catch (error) {
      console.error('Error generating Kundli:', error);
      const errorMessage = {
        id: nextMessageId(),
        text: "Sorry, Kundli generate karne mein koi problem aa rahi hai. Kripya dobara try karein ya contact karein.",
        sender: 'pandit',
        timestamp: new Date().toLocaleTimeString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsGeneratingKundli(false);
    }
  };

  const handleSendMessage = async () => {
    if (inputText.trim()) {
      const newMessage = {
        id: nextMessageId(),
        text: inputText,
        sender: 'user',
        timestamp: new Date().toLocaleTimeString()
      };
      
      setMessages([...messages, newMessage]);
      const currentInput = inputText;
      setInputText('');
      
      try {
        // Show typing indicator
        const typingMessage = {
          id: nextMessageId(),
          text: "Pandit ji typing...",
          sender: 'pandit',
          timestamp: new Date().toLocaleTimeString(),
          isTyping: true
        };
        setIsBotTyping(true);
        setMessages(prev => [...prev, typingMessage]);
        
        // Stepwise dialog
        let botText = '';
        if (currentStep === 'ask_name') {
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
            await new Promise(res => setTimeout(res, 150));
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
          // Regular chat with chart context; prefer Kundli data (has name and rich context)
          const chartContext = kundliData || chartData || null;
          const response = await astroBotAPI.sendChatMessage(currentInput, chartContext);
          botText = response.response;
          setCurrentStep('chatting');
        } else if (currentStep === 'generating') {
          botText = "Chart generate ho raha hai, kripya wait karein...";
        }

        // Smooth typing simulation with thoughtful delay for predictions (8s as requested)
        const looksLikePrediction = /\b(yog|shaadi|career|health|mangal|grah|kundli|prediction|yoga|marriage|job|business|future)\b/i.test(botText || '');
        const baseDelay = looksLikePrediction ? 8000 : 2000; // 8s for predictions, 2s for regular chat
        await new Promise(res => setTimeout(res, baseDelay));
        // Remove initial typing indicator before chunked responses
        setMessages(prev => prev.filter(msg => !msg.isTyping));
        // Split into 2-3 chunks and show an 8s typing window between chunks
        const parts = (botText || '').split(/\n\s*\n/).filter(Boolean).slice(0, 3);
        const sendChunk = async (idx) => {
          if (idx >= parts.length) return;
          // Show typing window for 8 seconds before each chunk
          const typingMsg = {
            id: nextMessageId(),
            text: 'Pandit ji typing...',
            sender: 'pandit',
            timestamp: new Date().toLocaleTimeString(),
            isTyping: true
          };
          setMessages(prev => ([...prev, typingMsg]));
          await new Promise(r => setTimeout(r, 8000));
          // Replace typing bubble with actual chunk
          setMessages(prev => {
            const withoutTyping = prev.filter(m => !m.isTyping);
            return [...withoutTyping, {
              id: nextMessageId(),
              text: parts[idx].trim(),
              sender: 'pandit',
              timestamp: new Date().toLocaleTimeString()
            }];
          });
          await sendChunk(idx + 1);
        };
        await sendChunk(0);
        // Backend now handles follow-up questions, so no need for separate frontend follow-up
        setIsBotTyping(false);
        
      } catch (error) {
        console.error('Error sending message:', error);
        
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

  if (!isOpen) return null;

  return (
    <div className={`expandable-chat-container ${isOpen ? 'expanded' : ''}`}>
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
                    onChartReady={() => {}}
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
                <div className="message-bubble">
                  <p>{message.text}</p>
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
          <div className="kundli-loading">
            <div className="loading-spinner"></div>
            <p>🔮 Aapka Kundli chart generate ho raha hai... Kripya wait karein</p>
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
          />
          <button 
            onClick={handleSendMessage} 
            className="send-button"
            disabled={isGeneratingKundli || isBotTyping}
          >
            <svg viewBox="0 0 24 24" className="send-icon">
              <path d="M22 2L11 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
          {/* Removed Edit details button per request */}
        </div>
      </div>
    </div>
  );
};

export default ExpandableChat;
