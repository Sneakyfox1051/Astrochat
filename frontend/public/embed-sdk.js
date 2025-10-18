/*
 * AstroRemedis Chat Embed SDK
 * Usage (on any website):
 * <script src="https://your-domain/embed-sdk.js" async></script>
 * <script>
 *   window.AstroRemedisChat.init({
 *     iframeUrl: 'https://your-domain', // built app URL (origin)
 *     width: 540,
 *     height: 868,
 *     position: 'right', // 'left' or 'right'
 *   });
 * </script>
 */
(function(){
  const STATE = { open: false, config: null };

  function createStyles(){
    if (document.getElementById('astroremedis-chat-styles')) return;
    const css = `
    .ar-chat-bubble{position:fixed;bottom:24px;right:24px;width:64px;height:64px;border-radius:50%;background:linear-gradient(135deg,#e46b00 0%,#ff8800 100%);box-shadow:0 10px 24px rgba(255,179,0,.45);display:flex;align-items:center;justify-content:center;cursor:pointer;z-index:999999;border:none}
    .ar-chat-bubble img{width:28px;height:28px}
    .ar-chat-frame{position:fixed;bottom:24px;right:24px;border:0;border-radius:16px;box-shadow:0 16px 48px rgba(0,0,0,.4);overflow:hidden;z-index:999999;background:#0f0f23;display:none}
    .ar-chat-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.35);backdrop-filter:blur(2px);z-index:999998;display:none}
    
    /* Dynamic responsive sizing */
    @media(max-width: 480px){
      .ar-chat-frame{width:95vw!important;height:90vh!important;right:2.5vw!important;left:2.5vw!important;bottom:2.5vh!important;top:2.5vh!important}
      .ar-chat-bubble{bottom:16px;right:16px;width:56px;height:56px}
      .ar-chat-bubble img{width:24px;height:24px}
    }
    @media(min-width: 481px) and (max-width: 768px){
      .ar-chat-frame{width:90vw!important;height:85vh!important;right:5vw!important;left:5vw!important;bottom:7.5vh!important;top:7.5vh!important}
      .ar-chat-bubble{bottom:20px;right:20px;width:60px;height:60px}
      .ar-chat-bubble img{width:26px;height:26px}
    }
    @media(min-width: 769px) and (max-width: 1024px){
      .ar-chat-frame{width:70vw!important;height:80vh!important;right:15vw!important;left:15vw!important;bottom:10vh!important;top:10vh!important}
    }
    @media(min-width: 1025px) and (max-width: 1440px){
      .ar-chat-frame{width:60vw!important;height:75vh!important;right:20vw!important;left:20vw!important;bottom:12.5vh!important;top:12.5vh!important}
    }
    @media(min-width: 1441px){
      .ar-chat-frame{width:50vw!important;height:70vh!important;right:25vw!important;left:25vw!important;bottom:15vh!important;top:15vh!important}
    }
    
    /* Landscape orientation adjustments */
    @media(max-height: 600px) and (orientation: landscape){
      .ar-chat-frame{height:95vh!important;top:2.5vh!important;bottom:2.5vh!important}
    }
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

  function getDynamicSize() {
    const width = window.innerWidth;
    const height = window.innerHeight;
    
    // Calculate optimal size based on screen dimensions
    if (width <= 480) {
      return { width: Math.min(width * 0.95, 400), height: Math.min(height * 0.9, 600) };
    } else if (width <= 768) {
      return { width: Math.min(width * 0.9, 600), height: Math.min(height * 0.85, 700) };
    } else if (width <= 1024) {
      return { width: Math.min(width * 0.7, 800), height: Math.min(height * 0.8, 800) };
    } else if (width <= 1440) {
      return { width: Math.min(width * 0.6, 900), height: Math.min(height * 0.75, 900) };
    } else {
      return { width: Math.min(width * 0.5, 1000), height: Math.min(height * 0.7, 1000) };
    }
  }

  function updateFrameSize() {
    const frame = document.getElementById('ar-chat-frame');
    if (!frame) return;
    
    const size = getDynamicSize();
    frame.style.width = size.width + 'px';
    frame.style.height = size.height + 'px';
  }

  function create(config){
    createStyles();
    STATE.config = config;
    const posRight = (config.position || 'right') === 'right';

    // Bubble
    const bubble = document.createElement('button');
    bubble.className = 'ar-chat-bubble';
    bubble.style.right = posRight ? '24px' : '';
    bubble.style.left = posRight ? '' : '24px';
    bubble.innerHTML = '<img alt="chat" src="'+(config.iconUrl||'https://gilded-baklava-db352f.netlify.app/Astro_LOGO.png')+'" />';
    bubble.addEventListener('click', () => { STATE.open ? close() : open(); });
    document.body.appendChild(bubble);

    // Backdrop
    const backdrop = document.createElement('div');
    backdrop.id = 'ar-chat-backdrop';
    backdrop.className = 'ar-chat-backdrop';
    backdrop.addEventListener('click', close);
    document.body.appendChild(backdrop);

    // Iframe
    const frame = document.createElement('iframe');
    frame.id = 'ar-chat-frame';
    frame.className = 'ar-chat-frame';
    frame.title = 'AstroRemedis Chat';
    frame.allow = 'camera; microphone; clipboard-read; clipboard-write;';
    frame.src = config.iframeUrl || 'https://gilded-baklava-db352f.netlify.app';
    
    // Use dynamic sizing instead of fixed config values
    const size = getDynamicSize();
    frame.style.width = size.width + 'px';
    frame.style.height = size.height + 'px';
    frame.style.right = posRight ? '24px' : '';
    frame.style.left = posRight ? '' : '24px';
    document.body.appendChild(frame);

    // Add resize listener for dynamic updates
    window.addEventListener('resize', updateFrameSize);
    window.addEventListener('orientationchange', () => {
      setTimeout(updateFrameSize, 100); // Small delay for orientation change
    });
  }

  window.AstroRemedisChat = {
    init: function(cfg){
      if (!cfg || !cfg.iframeUrl) {
        console.error('AstroRemedisChat: iframeUrl is required');
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


