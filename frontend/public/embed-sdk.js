/*
 * AstroRemedis Chat Embed SDK
 * Usage (on any website):
 * <script src="https://your-domain/embed-sdk.js" async></script>
 * <script>
 *   window.AstroRemedisChat.init({
 *     iframeUrl: 'https://your-domain', // built app URL (origin)
 *     width: 350,  // Fixed width in pixels
 *     height: 500, // Fixed height in pixels
 *   });
 * </script>
 * 
 * Universal size: Use width: 400, height: 700
 * This size works on both mobile and web devices
 */
(function(){
  const STATE = { open: false, config: null };

  function createStyles(){
    if (document.getElementById('astroremedis-chat-styles')) return;
    const css = `
    .ar-chat-bubble{position:fixed;bottom:24px;right:24px;width:64px;height:64px;border-radius:50%;background:linear-gradient(135deg,#e46b00 0%,#ff8800 100%);box-shadow:0 10px 24px rgba(255,179,0,.45);display:flex;align-items:center;justify-content:center;cursor:pointer;z-index:999999;border:none}
    .ar-chat-bubble img{width:28px;height:28px}
    .ar-chat-bubble .chat-icon{width:28px;height:28px;color:#ffffff}
    .ar-chat-frame{position:fixed;bottom:24px;right:24px;left:auto;width:400px;height:600px;border:0;border-radius:16px;box-shadow:0 16px 48px rgba(0,0,0,.4);overflow:hidden;z-index:999999;background:#0f0f23;display:none}
    .ar-chat-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.35);backdrop-filter:blur(2px);z-index:999998;display:none}
    `;
    const s = document.createElement('style');
    s.id = 'astroremedis-chat-styles';
    s.textContent = css;
    document.head.appendChild(s);
  }

  function open(){
    const frame = document.getElementById('ar-chat-frame');
    const backdrop = document.getElementById('ar-chat-backdrop');
    if (!frame) return;
    frame.style.display = 'block';
    if (backdrop) backdrop.style.display = 'block';
    STATE.open = true;
  }

  function close(){
    const frame = document.getElementById('ar-chat-frame');
    const backdrop = document.getElementById('ar-chat-backdrop');
    if (!frame) return;
    frame.style.display = 'none';
    if (backdrop) backdrop.style.display = 'none';
    STATE.open = false;
  }

  // Fixed sizing - no dynamic calculations

  function create(config){
    createStyles();
    STATE.config = config;
    
    // Get sizes from config - REQUIRED
    const width = config.width;
    const height = config.height;

    // Bubble
    const bubble = document.createElement('button');
    bubble.className = 'ar-chat-bubble';
    bubble.innerHTML = '<svg viewBox="0 0 24 24" class="chat-icon" style="width:28px;height:28px;color:#ffffff;"><path d="M21 12c0 4.418-4.03 8-9 8-1.068 0-2.09-.152-3.04-.433-.313-.095-.641-.143-.969-.143-.445 0-.885.09-1.292.266l-2.32 1.003c-.53.229-1.104-.27-.973-.83l.576-2.46c.087-.37.131-.752.131-1.135 0-.41-.06-.818-.177-1.211C2.34 13.633 2 12.343 2 11c0-4.418 4.03-8 9-8s10 3.582 10 9z" fill="currentColor"/><circle cx="8.5" cy="11.5" r="1" fill="#ffffff"/><circle cx="12" cy="11.5" r="1" fill="#ffffff"/><circle cx="15.5" cy="11.5" r="1" fill="#ffffff"/></svg>';
    bubble.addEventListener('click', () => { STATE.open ? close() : open(); });
    document.body.appendChild(bubble);

    // Backdrop
    const backdrop = document.createElement('div');
    backdrop.id = 'ar-chat-backdrop';
    backdrop.className = 'ar-chat-backdrop';
    backdrop.addEventListener('click', close);
    document.body.appendChild(backdrop);

    // Iframe with fixed sizing from config
    const frame = document.createElement('iframe');
    frame.id = 'ar-chat-frame';
    frame.className = 'ar-chat-frame';
    frame.title = 'AstroRemedis Chat';
    frame.allow = 'camera; microphone; clipboard-read; clipboard-write;';
    // For local testing, prefer local UI. Keep deployed URL commented for reference.
    // const DEFAULT_IFRAME_URL_DEPLOYED = 'https://gilded-baklava-db352f.netlify.app';
    frame.src = config.iframeUrl || 'http://localhost:3000';
    
    // Set fixed width and height directly from config
    frame.style.width = width + 'px';
    frame.style.height = height + 'px';
    
    document.body.appendChild(frame);
  }

  // Listen for messages from iframe to close the widget
  window.addEventListener('message', function(event) {
    // Security: Verify message source if needed (optional, adjust based on your domain)
    // if (event.origin !== 'https://your-domain.com') return;
    
    if (event.data && event.data.type === 'CLOSE_CHAT_WIDGET' && event.data.source === 'astroremedis-chat') {
      close();
      console.log('Received close message from iframe - closing widget');
    }
  });

  window.AstroRemedisChat = {
    init: function(cfg){
      if (!cfg || !cfg.iframeUrl) {
        console.error('AstroRemedisChat: iframeUrl is required');
        return;
      }
      if (!cfg.width || !cfg.height) {
        console.error('AstroRemedisChat: width and height are required. Recommended: 400x700 (works on both mobile and web).');
        return;
      }
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => create(cfg));
      } else {
        create(cfg);
      }
    }
  };
})();


