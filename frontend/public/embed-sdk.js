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
    .ar-chat-bubble .chat-icon{width:28px;height:28px;color:#ffffff}
    .ar-chat-frame{position:fixed;bottom:24px;right:24px;left:auto;width:400px;height:600px;border:0;border-radius:16px;box-shadow:0 16px 48px rgba(0,0,0,.4);overflow:hidden;z-index:999999;background:#0f0f23;display:none}
    .ar-chat-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.35);backdrop-filter:blur(2px);z-index:999998;display:none}
    
    /* Improved responsive sizing for mobile devices */
    @media(max-width: 360px){
      .ar-chat-frame{width:calc(100vw - 32px)!important;height:calc(100vh - 100px)!important;right:16px!important;left:16px!important;bottom:16px!important;top:auto!important;max-width:320px!important;max-height:500px!important}
      .ar-chat-bubble{bottom:16px;right:16px;width:50px;height:50px}
      .ar-chat-bubble img{width:22px;height:22px}
      .ar-chat-bubble .chat-icon{width:22px;height:22px}
    }
    @media(min-width: 361px) and (max-width: 480px){
      .ar-chat-frame{width:calc(100vw - 20px)!important;height:calc(100vh - 100px)!important;right:10px!important;left:10px!important;bottom:20px!important;top:auto!important;max-width:400px!important;max-height:650px!important}
      .ar-chat-bubble{bottom:20px;right:20px;width:56px;height:56px}
      .ar-chat-bubble img{width:24px;height:24px}
      .ar-chat-bubble .chat-icon{width:24px;height:24px}
    }
    @media(min-width: 481px) and (max-width: 768px){
      .ar-chat-frame{width:400px!important;height:600px!important;right:20px!important;left:auto!important;bottom:20px!important;top:auto!important}
      .ar-chat-bubble{bottom:20px;right:20px;width:60px;height:60px}
      .ar-chat-bubble img{width:26px;height:26px}
      .ar-chat-bubble .chat-icon{width:26px;height:26px}
    }
    @media(min-width: 769px){
      .ar-chat-frame{width:450px!important;height:700px!important;right:24px!important;left:auto!important;bottom:24px!important;top:auto!important}
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

  // Fixed sizing - no dynamic calculations

  function create(config){
    createStyles();
    STATE.config = config;
    const posRight = true; // Always position on the right

    // Bubble
    const bubble = document.createElement('button');
    bubble.className = 'ar-chat-bubble';
    bubble.style.right = '24px';
    bubble.style.left = '';
    bubble.innerHTML = '<svg viewBox="0 0 24 24" class="chat-icon" style="width:28px;height:28px;color:#ffffff;"><path d="M21 12c0 4.418-4.03 8-9 8-1.068 0-2.09-.152-3.04-.433-.313-.095-.641-.143-.969-.143-.445 0-.885.09-1.292.266l-2.32 1.003c-.53.229-1.104-.27-.973-.83l.576-2.46c.087-.37.131-.752.131-1.135 0-.41-.06-.818-.177-1.211C2.34 13.633 2 12.343 2 11c0-4.418 4.03-8 9-8s10 3.582 10 9z" fill="currentColor"/><circle cx="8.5" cy="11.5" r="1" fill="#ffffff"/><circle cx="12" cy="11.5" r="1" fill="#ffffff"/><circle cx="15.5" cy="11.5" r="1" fill="#ffffff"/></svg>';
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
    
    // Fixed sizing - CSS handles responsive behavior
    frame.style.right = '24px';
    frame.style.left = '';
    document.body.appendChild(frame);
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


