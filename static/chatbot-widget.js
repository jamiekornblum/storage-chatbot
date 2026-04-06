/**
 * Look Self Storage — Chat Widget
 *
 * EMBED ON YOUR WEBSITE — paste before </body>:
 *
 *   <script
 *     src="https://YOUR-BACKEND-URL/static/chatbot-widget.js"
 *     data-api-url="https://YOUR-BACKEND-URL/chat"
 *     data-title="Look Self Storage"
 *     data-color="#e87722"
 *   ></script>
 */

(function () {
  // ── Config ───────────────────────────────────────────────────────────────────
  const scriptTag   = document.currentScript || document.querySelector("script[data-api-url]");
  const API_URL     = scriptTag?.getAttribute("data-api-url")     || "/chat";
  const STREAM_URL  = scriptTag?.getAttribute("data-stream-url")  || (API_URL + "/stream");
  const ACCENT      = scriptTag?.getAttribute("data-color")       || "#cc0000";  // brand red
  const HEADER_BG   = scriptTag?.getAttribute("data-header-color")|| "#2a2a2a";  // charcoal

  // Suggestion chips shown on open — just shortcuts, user can also type freely
  const QUICK_REPLIES = [
    "I'd like to rent a unit",
    "View pricing & available sizes",
    "Office hours & gate access",
    "Vehicle, RV & boat storage",
    "Billing & payment options",
    "Security & facility features",
    "Request a callback",
    "Something else",
  ];

  // Size visualization data
  const SIZE_DETAILS = {
    "5x5":   { label: "5 × 5 ft",   sqft: 25,  analogy: "Like a large walk-in closet.",                   emoji: ["📦","🎿","🧳","🪣"],    items: ["10–15 small/medium boxes", "Seasonal & holiday items", "Sporting equipment", "Small appliances", "Documents & files"] },
    "5x10":  { label: "5 × 10 ft",  sqft: 50,  analogy: "About the size of a small bedroom.",             emoji: ["🛏","📦","📺","🧳"],    items: ["Twin or full mattress & frame", "Small sofa or loveseat", "TV & electronics", "15–20 boxes", "Bike or small equipment"] },
    "5x15":  { label: "5 × 15 ft",  sqft: 75,  analogy: "Like a large bedroom.",                          emoji: ["🛏","🛋","📦","📺"],    items: ["Queen mattress & frame", "Small living room set", "TV & electronics", "20–25 boxes", "Small appliances"] },
    "8x10":  { label: "8 × 10 ft",  sqft: 80,  analogy: "Between a bedroom and a one-car garage.",        emoji: ["🛏","🛋","📦","🖥"],    items: ["Queen mattress & frame", "Sofa & chairs", "Small dining set", "TV & appliances", "20–25 boxes"] },
    "10x10": { label: "10 × 10 ft", sqft: 100, analogy: "About the size of a standard bedroom.",          emoji: ["🛏","🛋","🍽️","📦","📺"], items: ["1–2 bedroom apartment contents", "Queen mattress + frame", "Sofa & chairs", "Dining table & chairs", "25–35 boxes", "TV & appliances"] },
    "10x15": { label: "10 × 15 ft", sqft: 150, analogy: "Like a large bedroom or small garage.",          emoji: ["🛏","🛋","🧺","📦","🖥"], items: ["2–3 bedroom home contents", "Multiple mattresses", "Full living room set", "Washer & dryer", "Large appliances", "35–45 boxes"] },
    "10x20": { label: "10 × 20 ft", sqft: 200, analogy: "About the size of a standard one-car garage.",  emoji: ["🚗","🛏","🛋","📦","🧺"], items: ["3–4 bedroom home contents", "Full furniture sets", "Large appliances", "Washer & dryer", "Small vehicle or motorcycle", "45–60 boxes"] },
    "10x25": { label: "10 × 25 ft", sqft: 250, analogy: "A full garage — fits a car with room to spare.", emoji: ["🚗","🏠","🛋","📦"],    items: ["Large home contents", "Full-size vehicle", "Multiple room sets", "Commercial inventory", "60–75 boxes"] },
    "10x30": { label: "10 × 30 ft", sqft: 300, analogy: "Like a two-car garage.",                        emoji: ["🚗","🚗","📦","🏗️"],   items: ["Large estate contents", "Two vehicles or a truck", "Contractor equipment", "Full business inventory", "75–100+ boxes"] },
    "10x40": { label: "10 × 40 ft", sqft: 400, analogy: "One of our largest — fits an entire household.", emoji: ["🚛","🏠","📦","🏗️"],   items: ["4+ bedroom estate", "Full moving truck contents", "Large vehicles or RV", "Commercial / contractor equipment", "100+ boxes"] },
  };

  function normalizeSizeKey(s) {
    return s.toLowerCase().replace(/[×x]/g, "x").replace(/\s/g, "");
  }

  // Location data for comparison card + distance calculation
  const LOCATIONS_DATA = [
    {
      label: "Highland",
      lat: 42.6539, lng: -83.6046,
      address: "500 N Milford Rd, Highland MI",
      highlights: ["24/7 kiosk access", "Climate-controlled units", "Electronic gate access"],
    },
    {
      label: "South Lyon",
      lat: 42.4714, lng: -83.6579,
      address: "59070 Oasis Center Dr, South Lyon MI",
      highlights: ["Widest unit selection", "Boat & RV outdoor parking", "Online reservations available"],
    },
    {
      label: "Lansing",
      lat: 42.7440, lng: -84.6135,
      address: "936 Mall Dr E, Lansing MI",
      highlights: ["Most affordable rates", "Boat & RV storage", "Drive-up access units"],
    },
  ];

  function haversineDistance(lat1, lng1, lat2, lng2) {
    const R = 3958.8;
    const toRad = d => d * Math.PI / 180;
    const dLat = toRad(lat2 - lat1);
    const dLng = toRad(lng2 - lng1);
    const a = Math.sin(dLat / 2) ** 2 +
              Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  const STORAGE_KEY = "ls_chat_v2";
  const STORAGE_TTL = 24 * 60 * 60 * 1000; // 24 hours

  const ICON_CHAT  = `<svg viewBox="0 0 24 24"><path d="M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2z"/></svg>`;
  const ICON_CLOSE = `<svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>`;

  // ── CSS ──────────────────────────────────────────────────────────────────────
  const style = document.createElement("style");
  style.textContent = `
    /* ── FAB button ── */
    #ls-chat-fab {
      position: fixed; bottom: 28px; right: 28px; z-index: 9998;
      width: 58px; height: 58px; border-radius: 50%;
      background: ${ACCENT}; border: none; cursor: pointer;
      box-shadow: 0 4px 20px rgba(0,0,0,.25);
      display: flex; align-items: center; justify-content: center;
      transition: transform .2s, box-shadow .2s;
    }
    #ls-chat-fab:hover { transform: scale(1.08); box-shadow: 0 6px 24px rgba(0,0,0,.3); }
    #ls-chat-fab svg { width: 26px; height: 26px; fill: #fff; }

    /* ── "Message me here" nudge label ── */
    #ls-chat-nudge {
      position: fixed; bottom: 38px; right: 98px; z-index: 9998;
      background: ${ACCENT}; color: #fff;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 13px; font-weight: 600;
      padding: 8px 14px; border-radius: 20px;
      box-shadow: 0 4px 16px rgba(0,0,0,.15);
      white-space: nowrap; cursor: pointer;
      transition: opacity .3s, transform .3s;
    }
    /* little arrow pointing right toward the FAB */
    #ls-chat-nudge::after {
      content: '';
      position: absolute; right: -7px; top: 50%; transform: translateY(-50%);
      border: 7px solid transparent;
      border-left-color: ${ACCENT};
      border-right-width: 0;
    }
    #ls-chat-nudge.ls-hidden { opacity: 0; pointer-events: none; transform: translateX(8px); }

    /* ── Chat window ── */
    #ls-chat-window {
      position: fixed; bottom: 100px; right: 28px; z-index: 9999;
      width: 440px; max-height: 600px;
      border-radius: 18px; overflow: hidden;
      box-shadow: 0 12px 48px rgba(0,0,0,.18);
      display: flex; flex-direction: column;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px; background: #fff;
      transition: opacity .25s, transform .25s;
    }
    #ls-chat-window.ls-hidden {
      opacity: 0; pointer-events: none; transform: translateY(16px);
    }

    /* ── Header ── */
    #ls-chat-header {
      background: ${HEADER_BG};
      padding: 14px 16px;
      display: flex; align-items: center; justify-content: space-between;
      flex-shrink: 0;
    }
    #ls-chat-header-left { display: flex; align-items: center; gap: 11px; }
    #ls-chat-avatar {
      width: 42px; height: 42px; border-radius: 8px;
      overflow: hidden; flex-shrink: 0;
      border: 1.5px solid rgba(255,255,255,.25);
    }
    #ls-chat-avatar svg { width: 100%; height: 100%; display: block; }
    #ls-chat-header-text { display: flex; flex-direction: column; gap: 3px; }
    #ls-chat-header-title { font-weight: 700; font-size: 16px; color: #fff; letter-spacing: .1px; }
    #ls-chat-header-sub {
      font-size: 11.5px; color: rgba(255,255,255,.75);
      display: flex; align-items: center; gap: 5px;
    }
    #ls-chat-header-sub::before {
      content: ''; display: inline-block;
      width: 6px; height: 6px; border-radius: 50%;
      background: #4ade80; flex-shrink: 0;
    }
    #ls-chat-close {
      background: none; border: none; cursor: pointer;
      display: flex; padding: 5px; border-radius: 8px;
      transition: background .15s;
    }
    #ls-chat-close:hover { background: rgba(255,255,255,.18); }
    #ls-chat-close svg { width: 18px; height: 18px; fill: #fff; }

    /* ── Messages ── */
    #ls-chat-messages {
      flex: 1; overflow-y: auto; padding: 18px 16px;
      display: flex; flex-direction: column; gap: 10px;
      background: #f7f7f8; scroll-behavior: smooth;
    }
    #ls-chat-messages::-webkit-scrollbar { width: 4px; }
    #ls-chat-messages::-webkit-scrollbar-thumb { background: #ddd; border-radius: 4px; }

    .ls-msg {
      max-width: 82%; padding: 10px 14px; border-radius: 16px;
      line-height: 1.55; word-break: break-word; font-size: 13.5px;
    }
    .ls-msg.ls-bot {
      background: #fff; color: #1a1a1a;
      border: 1px solid #ebebeb;
      align-self: flex-start; border-bottom-left-radius: 4px;
      box-shadow: 0 1px 3px rgba(0,0,0,.06);
    }
    .ls-msg.ls-user {
      background: ${ACCENT}; color: #fff;
      align-self: flex-end; border-bottom-right-radius: 4px;
    }
    .ls-msg strong { font-weight: 600; }
    .ls-msg a { color: ${ACCENT}; text-decoration: underline; word-break: break-all; }
    .ls-msg a:hover { opacity: .8; }
    .ls-msg ul { padding-left: 16px; margin: 4px 0 0; }
    .ls-msg li { margin-bottom: 2px; }

    /* ── Typing indicator ── */
    .ls-typing {
      display: flex; gap: 5px; padding: 11px 14px;
      background: #fff; border: 1px solid #ebebeb;
      border-radius: 16px; border-bottom-left-radius: 4px;
      align-self: flex-start; box-shadow: 0 1px 3px rgba(0,0,0,.06);
    }
    .ls-typing span {
      width: 7px; height: 7px; background: #c8c8c8; border-radius: 50%;
      animation: ls-bounce .9s infinite;
    }
    .ls-typing span:nth-child(2) { animation-delay: .15s; }
    .ls-typing span:nth-child(3) { animation-delay: .30s; }
    @keyframes ls-bounce {
      0%,60%,100% { transform: translateY(0); }
      30%          { transform: translateY(-5px); }
    }

    /* ── Quick reply chips ── */
    #ls-quick-replies {
      display: grid; grid-template-columns: 1fr 1fr; gap: 7px;
      padding: 0 0 2px; align-self: stretch;
    }
    .ls-quick-reply {
      background: #fff; border: 1.5px solid ${ACCENT}; color: ${ACCENT};
      border-radius: 20px; padding: 8px 10px; font-size: 12.5px;
      cursor: pointer; font-family: inherit; font-weight: 500;
      transition: background .15s, color .15s, transform .1s;
      text-align: center; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .ls-quick-reply:hover { background: ${ACCENT}; color: #fff; transform: translateY(-1px); }
    /* Last chip alone gets full width if odd count */
    .ls-quick-reply:last-child:nth-child(odd) { grid-column: span 2; }

    /* ── Size visualization card ── */
    .ls-size-card {
      align-self: flex-start; width: 100%;
      background: #fff; border: 1.5px solid #ebebeb;
      border-radius: 14px; padding: 14px 16px;
      box-shadow: 0 1px 4px rgba(0,0,0,.06);
    }
    .ls-size-card-header {
      display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;
    }
    .ls-size-card-label { font-size: 15px; font-weight: 700; color: #1a1a1a; }
    .ls-size-card-badge {
      font-size: 11px; font-weight: 700; color: #fff;
      background: ${ACCENT}; padding: 2px 9px; border-radius: 20px;
    }
    .ls-size-card-analogy { font-size: 12.5px; color: #777; margin: 4px 0 12px; }
    .ls-size-visual {
      background: #fff5f5; border: 2px dashed ${ACCENT};
      border-radius: 8px; margin-bottom: 12px;
      display: flex; flex-wrap: wrap; align-items: center;
      justify-content: center; gap: 6px; padding: 12px;
      font-size: 26px; min-height: 60px;
    }
    .ls-size-fits-title { font-size: 12px; font-weight: 700; color: #555; margin-bottom: 6px; }
    .ls-size-fits-list { list-style: none; padding: 0; margin: 0 0 12px; display: flex; flex-direction: column; gap: 4px; }
    .ls-size-fits-list li { font-size: 12.5px; color: #444; }
    .ls-size-fits-list li::before { content: "✓ "; color: ${ACCENT}; font-weight: 700; }
    .ls-size-reserve-btn {
      width: 100%; padding: 8px 0; border-radius: 20px;
      background: ${ACCENT}; border: none; color: #fff;
      font-size: 13px; font-weight: 600; font-family: inherit;
      cursor: pointer; transition: opacity .15s;
    }
    .ls-size-reserve-btn:hover { opacity: .88; }

    /* ── Reservation confirmation card ── */
    .ls-reservation-card {
      align-self: flex-start; max-width: 88%;
      background: #fff; border: 1.5px solid ${ACCENT};
      border-radius: 16px; border-bottom-left-radius: 4px;
      padding: 14px 16px; line-height: 1.5;
      box-shadow: 0 2px 8px rgba(0,0,0,.07);
    }
    .ls-reservation-card-title {
      font-weight: 700; font-size: 14px; color: ${ACCENT};
      display: flex; align-items: center; gap: 6px; margin-bottom: 10px;
    }
    .ls-reservation-card-title svg { width: 17px; height: 17px; fill: ${ACCENT}; flex-shrink: 0; }
    .ls-reservation-card table { font-size: 13px; border-collapse: collapse; width: 100%; }
    .ls-reservation-card td { padding: 3px 10px 3px 0; }
    .ls-reservation-card td:first-child { color: #999; white-space: nowrap; font-size: 12px; }
    .ls-reservation-card td:last-child { font-weight: 600; color: #1a1a1a; }
    .ls-reservation-card-footer {
      margin-top: 10px; font-size: 11.5px; color: #aaa;
      border-top: 1px solid #f0f0f0; padding-top: 9px;
    }
    .ls-complete-rental-btn {
      display: block; margin-top: 10px;
      background: ${ACCENT}; color: #fff; text-decoration: none;
      text-align: center; padding: 9px 14px; border-radius: 6px;
      font-size: 13px; font-weight: 600;
    }
    .ls-complete-rental-btn:hover { opacity: .88; }

    /* ── Callback form card ── */
    .ls-callback-card {
      align-self: flex-start; width: 88%;
      background: #fff; border: 1.5px solid ${ACCENT};
      border-radius: 16px; border-bottom-left-radius: 4px;
      padding: 14px 16px; box-shadow: 0 2px 8px rgba(0,0,0,.07);
    }
    .ls-callback-card-title {
      font-weight: 700; font-size: 14px; color: ${ACCENT}; margin-bottom: 12px;
    }
    .ls-callback-field {
      display: flex; flex-direction: column; gap: 4px; margin-bottom: 10px;
    }
    .ls-callback-field label { font-size: 11px; color: #999; font-weight: 600; text-transform: uppercase; letter-spacing: .4px; }
    .ls-callback-field input {
      border: 1.5px solid #e0e0e0; border-radius: 8px; padding: 8px 10px;
      font-size: 13px; font-family: inherit; outline: none;
    }
    .ls-callback-field input:focus { border-color: ${ACCENT}; }
    .ls-callback-submit {
      width: 100%; background: ${ACCENT}; color: #fff; border: none;
      border-radius: 8px; padding: 9px; font-size: 13px; font-weight: 600;
      font-family: inherit; cursor: pointer; margin-top: 4px;
    }
    .ls-callback-submit:hover { opacity: .88; }

    /* ── Location comparison card ── */
    .ls-location-card {
      align-self: flex-start; width: 100%;
      display: flex; flex-direction: row; gap: 10px;
      overflow-x: auto; padding-bottom: 6px;
      scroll-snap-type: x mandatory;
      -webkit-overflow-scrolling: touch;
    }
    .ls-location-card::-webkit-scrollbar { height: 4px; }
    .ls-location-card::-webkit-scrollbar-thumb { background: #ddd; border-radius: 4px; }
    .ls-location-tile {
      background: #fff; border: 1.5px solid #ebebeb;
      border-radius: 14px; padding: 13px 15px;
      box-shadow: 0 1px 4px rgba(0,0,0,.06);
      min-width: 220px; flex-shrink: 0;
      scroll-snap-align: start;
    }
    .ls-location-tile-header {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 4px;
    }
    .ls-location-tile-header strong { font-size: 14px; color: #1a1a1a; }
    .ls-location-dist {
      font-size: 11.5px; font-weight: 600; color: #fff;
      background: ${ACCENT}; padding: 2px 9px; border-radius: 20px;
    }
    .ls-location-tile-address { font-size: 11.5px; color: #aaa; margin-bottom: 8px; }
    .ls-location-tile-highlights { list-style: none; padding: 0; margin: 0 0 10px; display: flex; flex-direction: column; gap: 3px; }
    .ls-location-tile-highlights li { font-size: 12.5px; color: #555; }
    .ls-location-tile-highlights li::before { content: "✓ "; color: ${ACCENT}; font-weight: 700; }
    .ls-location-tile-btn {
      width: 100%; padding: 7px 0; border-radius: 20px;
      background: transparent; border: 1.5px solid ${ACCENT};
      color: ${ACCENT}; font-size: 12.5px; font-weight: 600;
      font-family: inherit; cursor: pointer;
      transition: background .15s, color .15s;
    }
    .ls-location-tile-btn:hover { background: ${ACCENT}; color: #fff; }

    /* ── Input area ── */
    #ls-chat-form {
      display: flex; gap: 8px; padding: 12px 14px;
      border-top: 1px solid #efefef; background: #fff; flex-shrink: 0;
    }
    #ls-chat-input {
      flex: 1; border: 1.5px solid #e5e5e5; border-radius: 22px;
      padding: 9px 16px; font-size: 13.5px; outline: none;
      font-family: inherit; color: #1a1a1a;
      transition: border-color .2s; background: #fafafa;
    }
    #ls-chat-input:focus { border-color: ${ACCENT}; background: #fff; }
    #ls-chat-input::placeholder { color: #bbb; }
    #ls-chat-send {
      width: 38px; height: 38px; border-radius: 50%; flex-shrink: 0;
      background: ${ACCENT}; border: none; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      transition: opacity .2s, transform .15s;
    }
    #ls-chat-send:hover:not(:disabled) { transform: scale(1.08); }
    #ls-chat-send:disabled { opacity: .35; cursor: default; }
    #ls-chat-send svg { width: 17px; height: 17px; fill: #fff; }

    /* ── Footer ── */
    #ls-chat-footer {
      text-align: center; padding: 0 14px 11px;
      font-size: 11px; color: #c8c8c8; background: #fff; flex-shrink: 0;
      letter-spacing: .1px;
    }
    #ls-chat-footer a { color: #c8c8c8; text-decoration: none; }
    #ls-chat-footer a:hover { color: #999; }

    @media (max-width: 500px) {
      #ls-chat-window { width: calc(100vw - 16px); right: 8px; bottom: 84px; }
      #ls-chat-fab { right: 16px; bottom: 16px; }
      #ls-chat-nudge { right: 86px; }
    }
  `;
  document.head.appendChild(style);

  // ── DOM ──────────────────────────────────────────────────────────────────────
  const nudge = document.createElement("div");
  nudge.id = "ls-chat-nudge";
  nudge.textContent = "Message me here";
  document.body.appendChild(nudge);

  const fab = document.createElement("button");
  fab.id = "ls-chat-fab";
  fab.setAttribute("aria-label", "Open chat");
  fab.innerHTML = ICON_CHAT;

  // Brand avatar — storage door panels inspired by the Look Self Storage logo
  const AVATAR_SVG = `
    <svg viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
      <rect x="0" y="0" width="20" height="40" fill="#2a2a2a"/>
      <rect x="20" y="0" width="20" height="40" fill="#cc0000"/>
      <rect x="3"  y="11" width="14" height="3" fill="#fff" rx="1"/>
      <rect x="3"  y="18" width="14" height="3" fill="#fff" rx="1"/>
      <rect x="3"  y="25" width="14" height="3" fill="#fff" rx="1"/>
      <rect x="23" y="11" width="14" height="3" fill="#fff" rx="1"/>
      <rect x="23" y="18" width="14" height="3" fill="#fff" rx="1"/>
      <rect x="23" y="25" width="14" height="3" fill="#fff" rx="1"/>
    </svg>`;

  const win = document.createElement("div");
  win.id = "ls-chat-window";
  win.classList.add("ls-hidden");
  win.innerHTML = `
    <div id="ls-chat-header">
      <div id="ls-chat-header-left">
        <div id="ls-chat-avatar">${AVATAR_SVG}</div>
        <div id="ls-chat-header-text">
          <div id="ls-chat-header-title">Stori</div>
          <div id="ls-chat-header-sub">Look Self Storage Assistant</div>
        </div>
      </div>
      <button id="ls-chat-close" aria-label="Close">
        <svg viewBox="0 0 24 24">
          <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
        </svg>
      </button>
    </div>
    <div id="ls-chat-messages"></div>
    <form id="ls-chat-form" autocomplete="off">
      <input id="ls-chat-input" type="text" placeholder="Ask about units, pricing, hours…" maxlength="500" />
      <button id="ls-chat-send" type="submit" aria-label="Send">
        <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
      </button>
    </form>
    <div id="ls-chat-footer">
      Powered by AI &mdash;
      <a href="https://www.lookselfstorage.com" target="_blank">lookselfstorage.com</a>
    </div>
  `;

  document.body.appendChild(fab);
  document.body.appendChild(win);

  // ── State ────────────────────────────────────────────────────────────────────
  let history               = [];   // [{role, content}] sent to API
  let displayLog            = [];   // [{role, text, card?}] for session restore
  let busy                  = false;
  let currentRecommendedSize = null; // last unit size Stori recommended

  const messagesEl = document.getElementById("ls-chat-messages");
  const input      = document.getElementById("ls-chat-input");
  const sendBtn    = document.getElementById("ls-chat-send");

  // ── Session persistence ──────────────────────────────────────────────────────
  function saveSession() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        ts: Date.now(), history, displayLog,
      }));
    } catch {}
  }

  function restoreSession() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return false;
      const saved = JSON.parse(raw);
      if (Date.now() - saved.ts > STORAGE_TTL) {
        localStorage.removeItem(STORAGE_KEY);
        return false;
      }
      history    = saved.history    || [];
      displayLog = saved.displayLog || [];
      displayLog.forEach(m => {
        if (m.card) renderConfirmationCard(m.card);
        else        addBubble(m.role, m.text);
      });
      return displayLog.length > 0;
    } catch { return false; }
  }

  // Inject a hidden session-context note at position 0 of the API history
  // so Stori always knows whether this is a new or returning visitor.
  function injectSessionContext(isReturning) {
    const note = isReturning
      ? "[SYSTEM NOTE — not visible to customer] This customer is returning within the same session. You have already spoken with them. Do not re-introduce yourself. Pick up naturally from where the conversation left off."
      : "[SYSTEM NOTE — not visible to customer] This is a brand new customer starting a fresh conversation. Introduce yourself as Stori and welcome them.";
    // Only inject if not already present
    if (history.length === 0 || history[0].content !== note) {
      history.unshift({ role: "user", content: note });
      history.splice(1, 0, { role: "assistant", content: "Understood." });
    }
  }

  // ── Text formatting ──────────────────────────────────────────────────────────
  function escapeHtml(t) {
    return t.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  }

  function formatText(text) {
    // Process markdown links [label](url) before escaping so URLs survive intact
    const linkRe = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
    const segments = [];
    let last = 0, m;
    while ((m = linkRe.exec(text)) !== null) {
      segments.push({ type: "text", v: text.slice(last, m.index) });
      segments.push({ type: "link", label: m[1], url: m[2] });
      last = m.index + m[0].length;
    }
    segments.push({ type: "text", v: text.slice(last) });

    return segments.map(s => {
      if (s.type === "link") {
        return `<a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.label)}</a>`;
      }
      return escapeHtml(s.v.trim())
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/\n{3,}/g, "\n\n")
        .replace(/\n\n/g, "<br><br>")
        .replace(/\n/g, "<br>");
    }).join("");
  }

  // Strip the CHIPS line from text and return { cleanText, chips[] }
  function parseChips(text) {
    const match = text.match(/\n?CHIPS:\s*(.+)$/m);
    if (!match) return { cleanText: text, chips: [] };
    const chips = match[1].split("|").map(c => c.trim()).filter(Boolean);
    const cleanText = text.slice(0, match.index).trim();
    return { cleanText, chips };
  }

  // Strip any partial or complete CHIPS directive for live display during streaming
  function stripChipsForDisplay(text) {
    return text.replace(/\n?CHIPS:.*$/ms, '').trim();
  }

  // ── Message helpers ──────────────────────────────────────────────────────────
  function addBubble(role, text) {
    const div = document.createElement("div");
    div.className = "ls-msg " + (role === "user" ? "ls-user" : "ls-bot");
    div.innerHTML = formatText(text);
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function showTyping() {
    const div = document.createElement("div");
    div.className = "ls-msg ls-bot ls-typing";
    div.id = "ls-typing-ind";
    div.innerHTML = "<span></span><span></span><span></span>";
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function hideTyping() {
    document.getElementById("ls-typing-ind")?.remove();
  }

  function removeQuickReplies() {
    document.getElementById("ls-quick-replies")?.remove();
  }

  // ── Reservation confirmation card ────────────────────────────────────────────
  function renderConfirmationCard(meta) {
    const card = document.createElement("div");
    card.className = "ls-reservation-card";
    card.innerHTML = `
      <div class="ls-reservation-card-title">
        <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
        Reservation Received!
      </div>
      <table>
        <tr><td>Name</td><td>${escapeHtml(meta.name)}</td></tr>
        <tr><td>Unit</td><td>${escapeHtml(meta.unit_size)}</td></tr>
        <tr><td>Ref #</td><td>${meta.reservation_id}</td></tr>
      </table>
      <div class="ls-reservation-card-footer">
        Check your email for a link to pay, sign your lease, and move in — same-day move-in available!
      </div>
      <a href="https://www.lookselfstorage.com" target="_blank" rel="noopener noreferrer" class="ls-complete-rental-btn">Complete your rental online →</a>
    `;
    messagesEl.appendChild(card);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return card;
  }

  // ── Quick reply chip renderer ────────────────────────────────────────────────
  const OPEN_ENDED_CHIPS   = /^(something else|other)$/i;
  const SEE_WHAT_FITS_CHIP = /^see what fits/i;
  const GOOGLE_REVIEW_CHIP  = /^please leave a google review$/i;
  const CALLBACK_CHIP       = /^request a callback$/i;
  const YES_MORE_CHIP       = /^yes, one more thing$/i;
  const GOOGLE_REVIEW_URL  = "https://search.google.com/local/writereview?placeid=ChIJV4YgHEBfI4gRoATFFK2mfoU";

  function showChips(options, onSelect) {
    removeQuickReplies();
    const chips = document.createElement("div");
    chips.id = "ls-quick-replies";
    options.forEach(label => {
      const btn = document.createElement("button");
      btn.className = "ls-quick-reply";
      btn.textContent = label;
      btn.addEventListener("click", () => {
        removeQuickReplies();
        if (OPEN_ENDED_CHIPS.test(label)) {
          input.placeholder = "Type your question…";
          input.focus();
        } else if (SEE_WHAT_FITS_CHIP.test(label)) {
          if (currentRecommendedSize) renderSizeVisualization(currentRecommendedSize);
        } else if (YES_MORE_CHIP.test(label)) {
          addBubble("user", label);
          setTimeout(() => showMainChips(), 300);
        } else if (CALLBACK_CHIP.test(label)) {
          addBubble("user", label);
          setTimeout(() => {
            addBubble("bot", "Sure! Leave your details and we'll have the right office give you a call.");
            const card = document.createElement("div");
            card.className = "ls-callback-card";
            card.innerHTML = `
              <div class="ls-callback-card-title">📞 Request a Callback</div>
              <div class="ls-callback-field">
                <label>Your Name</label>
                <input type="text" id="ls-cb-name" placeholder="Jane Smith" />
              </div>
              <div class="ls-callback-field">
                <label>Phone Number</label>
                <input type="tel" id="ls-cb-phone" placeholder="(555) 123-4567" />
              </div>
              <div class="ls-callback-field">
                <label>Which Location?</label>
                <select id="ls-cb-location" style="border:1.5px solid #e0e0e0;border-radius:8px;padding:8px 10px;font-size:13px;font-family:inherit;outline:none;">
                  <option value="">Select a location…</option>
                  <option value="highland">Highland</option>
                  <option value="lansing">Lansing</option>
                  <option value="south_lyon">South Lyon</option>
                </select>
              </div>
              <div class="ls-callback-field">
                <label>What can we help you with?</label>
                <input type="text" id="ls-cb-notes" placeholder="e.g. pricing, unit availability, moving out…" />
              </div>
              <button class="ls-callback-submit" id="ls-cb-submit">Submit →</button>
            `;
            messagesEl.appendChild(card);
            messagesEl.scrollTop = messagesEl.scrollHeight;
            document.getElementById("ls-cb-submit").addEventListener("click", () => {
              const name     = document.getElementById("ls-cb-name").value.trim();
              const phone    = document.getElementById("ls-cb-phone").value.trim();
              const location = document.getElementById("ls-cb-location").value;
              const notes    = document.getElementById("ls-cb-notes").value.trim();
              document.getElementById("ls-cb-name").style.borderColor     = name     ? "" : "#cc0000";
              document.getElementById("ls-cb-phone").style.borderColor    = phone    ? "" : "#cc0000";
              document.getElementById("ls-cb-location").style.borderColor = location ? "" : "#cc0000";
              if (!name || !phone || !location) return;
              card.remove();
              fetch(BASE_URL + "/callback", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, phone, location, notes }),
              });
              const locLabel = { highland: "Highland", lansing: "Lansing", south_lyon: "South Lyon" }[location];
              addBubble("bot", `Perfect, ${name}! The ${locLabel} team will call you at ${phone} during office hours — Tue–Fri 9:30 AM–6 PM or Sat 8 AM–4:30 PM.${notes ? " We'll make sure they know you're asking about: " + notes + "." : ""}`);
              showMainChips();
            });
          }, 400);
        } else if (GOOGLE_REVIEW_CHIP.test(label)) {
          addBubble("user", label);
          window.open(GOOGLE_REVIEW_URL, "_blank", "noopener,noreferrer");
          setTimeout(() => {
            addBubble("bot", "Thanks so much — it really means a lot to us! 😊 Have a great day!");
            setTimeout(() => resetChat(), 60000);
          }, 400);
        } else {
          onSelect(label);
        }
      });
      chips.appendChild(btn);
    });
    messagesEl.appendChild(chips);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  // ── Location comparison card ─────────────────────────────────────────────────
  function showLocationComparison(userLat, userLng) {
    removeQuickReplies();

    // Attach distances and sort nearest-first if we have the user's location
    const locs = LOCATIONS_DATA.map(loc => ({
      ...loc,
      distance: (userLat != null)
        ? haversineDistance(userLat, userLng, loc.lat, loc.lng)
        : null,
    }));
    if (userLat != null) locs.sort((a, b) => a.distance - b.distance);

    const card = document.createElement("div");
    card.className = "ls-location-card";

    locs.forEach(loc => {
      const tile = document.createElement("div");
      tile.className = "ls-location-tile";

      const distBadge = loc.distance != null
        ? `<span class="ls-location-dist">${loc.distance.toFixed(1)} mi away</span>`
        : "";

      const highlightItems = loc.highlights
        .map(h => `<li>${escapeHtml(h)}</li>`)
        .join("");

      tile.innerHTML = `
        <div class="ls-location-tile-header">
          <strong>${escapeHtml(loc.label)}</strong>${distBadge}
        </div>
        <div class="ls-location-tile-address">${escapeHtml(loc.address)}</div>
        <ul class="ls-location-tile-highlights">${highlightItems}</ul>
      `;

      const btn = document.createElement("button");
      btn.className = "ls-location-tile-btn";
      btn.textContent = `Choose ${loc.label}`;
      btn.addEventListener("click", () => {
        card.remove();
        sendMessage(loc.label);
      });
      tile.appendChild(btn);
      card.appendChild(tile);
    });

    messagesEl.appendChild(card);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  // ── Size visualization ───────────────────────────────────────────────────────
  function renderSizeVisualization(sizeKey) {
    const detail = SIZE_DETAILS[normalizeSizeKey(sizeKey)];
    if (!detail) return;
    removeQuickReplies();

    const [w, h] = normalizeSizeKey(sizeKey).split("x").map(Number);
    const maxW = 180, scale = maxW / Math.max(w, h);
    const dispW = Math.round(w * scale), dispH = Math.round(h * scale);

    const card = document.createElement("div");
    card.className = "ls-size-card";
    card.innerHTML = `
      <div class="ls-size-card-header">
        <span class="ls-size-card-label">${detail.label}</span>
        <span class="ls-size-card-badge">${detail.sqft} sq ft</span>
      </div>
      <p class="ls-size-card-analogy">${detail.analogy}</p>
      <div class="ls-size-visual" style="width:${dispW}px;min-height:${dispH}px;">
        ${detail.emoji.map(e => `<span>${e}</span>`).join("")}
      </div>
      <p class="ls-size-fits-title">What fits:</p>
      <ul class="ls-size-fits-list">
        ${detail.items.map(i => `<li>${escapeHtml(i)}</li>`).join("")}
      </ul>
    `;

    const btn = document.createElement("button");
    btn.className = "ls-size-reserve-btn";
    btn.textContent = `Reserve a ${detail.label} unit`;
    btn.addEventListener("click", () => {
      card.remove();
      sendMessage(`I'd like to reserve a ${detail.label} unit`);
    });
    card.appendChild(btn);

    messagesEl.appendChild(card);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  // ── Inactivity reset (30 min) ────────────────────────────────────────────────
  const INACTIVITY_MS = 30 * 60 * 1000;
  let inactivityTimer = null;

  function resetInactivityTimer() {
    clearTimeout(inactivityTimer);
    inactivityTimer = setTimeout(() => resetChat(), INACTIVITY_MS);
  }

  // ── Reset ────────────────────────────────────────────────────────────────────
  function resetChat() {
    clearTimeout(inactivityTimer);
    history    = [];
    displayLog = [];
    busy       = false;
    sendBtn.disabled = false;
    messagesEl.innerHTML = "";
    removeQuickReplies();
    localStorage.removeItem(STORAGE_KEY);
    showGreeting();
  }

  // ── Greeting ─────────────────────────────────────────────────────────────────
  function showGreeting() {
    const text = "Hi! I'm Stori, your storage guide at Look Self Storage 👋\nWhat can I help you with today?";
    addBubble("bot", text);
    // Not saved to displayLog — greeting is always shown fresh, never replayed from session
    showMainChips();
  }

  function showMainChips() {
    showChips(QUICK_REPLIES, q => sendMessage(q));
  }

  const RESET_PATTERN    = /\b(restart|reset|start over|stop|exit|cancel|new conversation|begin again|never mind|nevermind|done|that's all|that is all|no thanks|i'm good|im good)\b/i;

  // ── Send message ─────────────────────────────────────────────────────────────
  async function sendMessage(text) {
    if (!text.trim() || busy) return;
    resetInactivityTimer();

    if (RESET_PATTERN.test(text)) {
      resetChat();
      return;
    }

    if (/^not sure yet$/i.test(text.trim())) {
      addBubble("user", text);
      displayLog.push({ role: "user", text });
      history.push({ role: "user", content: text });
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          pos => showLocationComparison(pos.coords.latitude, pos.coords.longitude),
          ()   => showLocationComparison(null, null),
          { timeout: 5000 }
        );
      } else {
        showLocationComparison(null, null);
      }
      return;
    }

    busy = true;
    sendBtn.disabled = true;
    removeQuickReplies();

    addBubble("user", text);
    displayLog.push({ role: "user", text });
    history.push({ role: "user", content: text });

    showTyping();

    let fullReply = "";
    let reservationMeta = null;
    let streamWorked = false;

    // Try streaming endpoint first
    try {
      const res = await fetch(STREAM_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history }),
      });

      if (res.ok && res.body) {
        hideTyping();
        const botDiv  = addBubble("bot", "");
        const reader  = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop();

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const payload = JSON.parse(line.slice(6));
              if (payload.text) {
                fullReply += payload.text;
                botDiv.innerHTML = formatText(stripChipsForDisplay(fullReply));
                messagesEl.scrollTop = messagesEl.scrollHeight;
              }
              if (payload.error) {
                fullReply = payload.error;
                botDiv.innerHTML = formatText(fullReply);
              }
              if (payload.done && payload.metadata) {
                reservationMeta = payload.metadata;
              }
            } catch {}
          }
        }
        // Parse and strip CHIPS directive from streamed reply
        if (fullReply) {
          const { cleanText, chips } = parseChips(fullReply);
          if (cleanText !== fullReply) {
            botDiv.innerHTML = formatText(cleanText);
            fullReply = cleanText;
          }
          // Track the last unit size Stori recommended so "See what fits" works
          const sizeMatch = fullReply.match(/\b(\d+)[x×](\d+)\b/i);
          if (sizeMatch) currentRecommendedSize = normalizeSizeKey(sizeMatch[0]);
          if (chips.length) showChips(chips, q => sendMessage(q));
        }

        streamWorked = true;
      }
    } catch {}

    // Fallback: non-streaming
    if (!streamWorked) {
      hideTyping();
      try {
        const res  = await fetch(API_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ messages: history }),
        });
        const data = await res.json();
        fullReply = data.reply || data.error || "Sorry, I couldn't get a response. Please try again.";
        if (data.metadata) reservationMeta = data.metadata;
        const { cleanText, chips } = parseChips(fullReply);
        fullReply = cleanText;
        const szFallback = fullReply.match(/\b(\d+)[x×](\d+)\b/i);
        if (szFallback) currentRecommendedSize = normalizeSizeKey(szFallback[0]);
        addBubble("bot", fullReply);
        if (chips.length) showChips(chips, q => sendMessage(q));
      } catch {
        fullReply = "Connection error. Please check your internet and try again.";
        addBubble("bot", fullReply);
      }
    }

    // Show reservation confirmation card if a reservation was created
    if (reservationMeta?.type === "reservation_created") {
      renderConfirmationCard(reservationMeta);
      displayLog.push({ card: reservationMeta });
      if (fullReply) {
        history.push({ role: "assistant", content: fullReply });
        displayLog.push({ role: "bot", text: fullReply });
        saveSession();
      }
      busy = false;
      sendBtn.disabled = false;
      showMainChips();
      return;
    }

    if (fullReply) {
      history.push({ role: "assistant", content: fullReply });
      displayLog.push({ role: "bot", text: fullReply });
      saveSession();
    }

    busy = false;
    sendBtn.disabled = false;
    input.placeholder = "Ask about units, pricing, hours…";
    input.focus();
  }

  function openChat() {
    nudge.classList.add("ls-hidden");
    win.classList.remove("ls-hidden");
    fab.innerHTML = ICON_CLOSE;
    if (messagesEl.children.length === 0) {
      const isReturning = restoreSession();
      injectSessionContext(isReturning);
      resetInactivityTimer();
      if (!isReturning) {
        showGreeting();
      } else {
        // Restore chips so customer always has options visible
        showMainChips();
      }
    }
    setTimeout(() => input.focus(), 50);
  }

  // ── Events ───────────────────────────────────────────────────────────────────
  nudge.addEventListener("click", openChat);

  fab.addEventListener("click", () => {
    const isOpen = !win.classList.contains("ls-hidden");
    if (isOpen) {
      win.classList.add("ls-hidden");
      fab.innerHTML = ICON_CHAT;
    } else {
      openChat();
    }
  });

  document.getElementById("ls-chat-close").addEventListener("click", () => {
    win.classList.add("ls-hidden");
    fab.innerHTML = ICON_CHAT;
  });

  document.getElementById("ls-chat-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    input.value = "";
    sendMessage(text);
  });
})();
