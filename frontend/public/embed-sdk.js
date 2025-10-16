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
    @media(max-width:620px){.ar-chat-frame{width:96vw!important;height:86vh!important;right:2vw!important;left:2vw!important}}
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
    frame.style.width = (config.width||540)+'px';
    frame.style.height = (config.height||868)+'px';
    frame.style.right = posRight ? '24px' : '';
    frame.style.left = posRight ? '' : '24px';
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


