/* PayPal Credit Agent — v9 Matching Mini App */

const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); }

const API = '/api';
let busy = false, flowState = 'idle', chosenOffer = null;
let userName = '', userEmail = '';
// Check if opened for login — hash may come as #login or encoded
let openedForLogin = window.location.hash.includes('login') ||
                     window.location.href.includes('#login') ||
                     window.location.search.includes('mode=login');

const OFFERS = [
  { tag:'Best Match', name:'PayPal Pay Later', amt:'$2,500', score:96, detail:'0% APR · 6 months · No annual fee' },
  { tag:'Premium', name:'PayPal Cashback Mastercard', amt:'$5,000', score:84, detail:'3% cashback on all PayPal purchases' },
  { tag:'Starter', name:'PayPal Credit Line', amt:'$1,200', score:71, detail:'Build credit history · 19.99% APR' },
];

const TXNS = [
  {icon:'👟',name:'Nike.com',cat:'Sports & Fitness',amt:'-$129.00',date:'Apr 1'},
  {icon:'🍔',name:'Uber Eats',cat:'Food & Drink',amt:'-$24.50',date:'Mar 30'},
  {icon:'📦',name:'Amazon',cat:'Shopping',amt:'-$67.99',date:'Mar 28'},
  {icon:'☕',name:'Starbucks',cat:'Coffee',amt:'-$8.75',date:'Mar 27'},
  {icon:'🎵',name:'Spotify',cat:'Subscriptions',amt:'-$9.99',date:'Mar 25'},
  {icon:'🛒',name:'Target',cat:'Shopping',amt:'-$45.20',date:'Mar 23'},
  {icon:'🎬',name:'Netflix',cat:'Subscriptions',amt:'-$15.99',date:'Mar 20'},
  {icon:'💳',name:'PayPal Credit',cat:'Payment Received',amt:'+$200.00',date:'Mar 15',cr:true},
];

// ── Helpers ──
const $ = id => document.getElementById(id);
const bg = () => $('chatBg');
const now = () => { const d=new Date(); return d.getHours().toString().padStart(2,'0')+':'+d.getMinutes().toString().padStart(2,'0'); };
const sleep = ms => new Promise(r=>setTimeout(r,ms));
const scroll = () => bg().scrollTop = 999999;

function makeRow(type) {
  const el = document.createElement('div');
  el.className = `row ${type}`;
  bg().appendChild(el);
  return el;
}

function addBubble(type, html, wide) {
  const row = makeRow(type);
  const bbl = document.createElement('div');
  bbl.className = `bbl${wide ? ' bbl-wide' : ''}`;
  bbl.innerHTML = html;
  row.appendChild(bbl);
  requestAnimationFrame(() => requestAnimationFrame(() => { row.classList.add('show'); scroll(); }));
  return row;
}

function addTs(row, type) {
  const ts = document.createElement('div');
  ts.className = 'ts';
  ts.innerHTML = type === 'out' ? `${now()} <span class="ticks">✓✓</span>` : now();
  row.querySelector('.bbl').appendChild(ts);
}

function showTyping() {
  const row = makeRow('inc');
  row.classList.add('typing-row','show');
  row.id = 'typing';
  const bbl = document.createElement('div');
  bbl.className = 'bbl tbbl';
  bbl.innerHTML = '<div class="td"></div><div class="td"></div><div class="td"></div>';
  row.appendChild(bbl);
  scroll();
  return row;
}

function rmTyping() { const t = $('typing'); if (t) t.remove(); }

// ── Dummy Login ──
function showLogin() { $('loginOverlay').classList.add('show'); }

async function handleLogin() {
  const btn = $('loginBtn');
  btn.textContent = 'Logging in...';
  btn.classList.add('loading');
  await sleep(1500);
  btn.textContent = '✓ Connected';
  btn.classList.remove('loading');
  btn.classList.add('done');
  await sleep(600);

  // If opened from bot chat for login, send data back and close
  if (openedForLogin) {
    const email = $('loginEmail').value || 'user@email.com';
    const pass = $('loginPass').value;
    if (!email) { btn.textContent = 'Log In'; btn.classList.remove('loading'); return; }
    const name = email.split('@')[0].replace(/[._]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

    // Show success state
    btn.textContent = '✓ Connected — Returning to chat...';
    await sleep(800);

    // Send data to bot and close Mini App
    if (tg) {
      try {
        tg.sendData(JSON.stringify({ action: 'login_complete', user: name, email: email }));
      } catch(e) { console.log('sendData error:', e); }
      await sleep(500);
      try { tg.close(); } catch(e) { console.log('close error:', e); }
    }

    // Fallback — show "return to chat" message if close didn't work
    await sleep(1000);
    document.querySelector('.login-card').innerHTML = `
      <div style="text-align:center;padding:20px">
        <div style="font-size:2rem;margin-bottom:12px">✅</div>
        <div style="font-size:16px;font-weight:700;color:#003087;margin-bottom:8px">Connected as ${name}</div>
        <div style="font-size:13px;color:#666;margin-bottom:16px">Close this window to return to the bot chat.</div>
        <div style="font-size:12px;color:#999">The bot will continue the credit flow automatically.</div>
      </div>`;
    return;
  }

  // Otherwise continue in Mini App — store user info
  const emailVal = $('loginEmail').value || 'user@email.com';
  userName = emailVal.split('@')[0].replace(/[._]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  userEmail = emailVal;

  $('loginOverlay').classList.remove('show');
  const acBtn = document.querySelector('.ac-btn');
  if (acBtn) { acBtn.textContent = '✓ Connected'; acBtn.classList.add('done'); }
  let r = addBubble('out', 'Connected ✓'); addTs(r, 'out');
  await sleep(400);
  await runScoring();
}

// ── Mock Screens ──
function openScreen(type) {
  if (type === 'statement') buildStatement();
  if (type === 'card') buildCardManage();
  $('screen-' + type).classList.add('open');
}

function closeScreen() {
  document.querySelectorAll('.mock-screen').forEach(s => s.classList.remove('open'));
}

function buildStatement() {
  const o = OFFERS[chosenOffer ?? 0];
  const lim = parseFloat(o.amt.replace(/[^0-9.]/g, ''));
  $('stmt-body').innerHTML = `
    <div class="stmt-card">
      <div class="sc-lbl">Current Balance</div>
      <div class="sc-amt">$847.23</div>
      <div class="sc-meta-row">
        <div class="sc-meta-item"><div class="ml">AVAILABLE</div><div class="mv hi">$${(lim-847.23).toFixed(2)}</div></div>
        <div class="sc-meta-item"><div class="ml">DUE DATE</div><div class="mv">Apr 15</div></div>
        <div class="sc-meta-item"><div class="ml">MIN PAYMENT</div><div class="mv">$25.00</div></div>
      </div>
      <button class="stmt-pay-btn" onclick="alert('Payment feature coming soon!')">Pay Now</button>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
      <div style="font-size:13px;font-weight:900;color:rgba(255,255,255,0.65)">Recent Transactions</div>
      <div style="font-size:12px;color:var(--blue);cursor:pointer">Filter</div>
    </div>
    <div class="txn-list">
      ${TXNS.map(t => `
        <div class="txn">
          <div class="txn-ic">${t.icon}</div>
          <div class="txn-info"><div class="txn-name">${t.name}</div><div class="txn-cat">${t.cat}</div></div>
          <div class="txn-right"><div class="txn-amt${t.cr ? ' cr' : ''}">${t.amt}</div><div class="txn-date">${t.date}</div></div>
        </div>
      `).join('')}
    </div>`;
}

function buildCardManage() {
  const o = OFFERS[chosenOffer ?? 0];
  $('screen-card').querySelector('.sc-sub').textContent = o.name;
  $('card-body').innerHTML = `
    <div class="vcard">
      <div class="vc-shine"></div>
      <div class="vc-top"><div class="vc-brand">PayPal</div><div class="vc-type">CREDIT</div></div>
      <div class="vc-num" id="vcNum">•••• •••• •••• 4821</div>
      <div class="vc-bot">
        <div><div class="vc-label">CARDHOLDER</div><div class="vc-val">${(userName || 'USER').toUpperCase()}</div></div>
        <div><div class="vc-label">EXPIRES</div><div class="vc-val">09/28</div></div>
      </div>
    </div>
    <div class="csr-row">
      <div class="csr" onclick="alert('Card frozen!')"><span class="ci">🧊</span><span class="cl">Freeze</span></div>
      <div class="csr" onclick="alert('Replacement requested')"><span class="ci">🔄</span><span class="cl">Replace</span></div>
      <div class="csr" onclick="alert('Report filed')"><span class="ci">⚠️</span><span class="cl">Report</span></div>
      <div class="csr" onclick="alert('PIN sent to email')"><span class="ci">🔑</span><span class="cl">PIN</span></div>
    </div>
    <div class="mc-sec">
      <div class="mc-sec-hd">Spending Limit</div>
      <div class="limit-wrap">
        <div class="lw-top"><span>Monthly Limit</span><span class="lw-val">${o.amt}</span></div>
        <div class="lw-bar"><div class="lw-fill" style="width:33.9%"></div></div>
        <div class="lw-sub"><span>$847.23 used · 33.9%</span><span>of ${o.amt}</span></div>
      </div>
    </div>
    <div class="mc-sec">
      <div class="mc-sec-hd">Controls</div>
      <div class="trow"><div class="trow-left"><span>🌐</span><span class="trow-name">Online Purchases</span></div><div class="tog on" onclick="this.classList.toggle('on');this.classList.toggle('off')"><div class="tog-k"></div></div></div>
      <div class="trow"><div class="trow-left"><span>✈️</span><span class="trow-name">International</span></div><div class="tog off" onclick="this.classList.toggle('on');this.classList.toggle('off')"><div class="tog-k"></div></div></div>
      <div class="trow"><div class="trow-left"><span>📱</span><span class="trow-name">Contactless</span></div><div class="tog on" onclick="this.classList.toggle('on');this.classList.toggle('off')"><div class="tog-k"></div></div></div>
      <div class="trow"><div class="trow-left"><span>🔔</span><span class="trow-name">Spend Alerts</span></div><div class="tog on" onclick="this.classList.toggle('on');this.classList.toggle('off')"><div class="tog-k"></div></div></div>
    </div>
    <div class="mc-sec">
      <div class="mc-sec-hd">Card Details</div>
      <div class="det-row"><span class="det-lbl">Card Number</span><span class="det-val" id="cdNum">•••• •••• •••• 4821</span><span class="det-show" onclick="toggleCardNum()">Show</span></div>
      <div class="det-row"><span class="det-lbl">CVV</span><span class="det-val" id="cdCvv">•••</span><span class="det-show" onclick="toggleCVV()">Show</span></div>
      <div class="det-row"><span class="det-lbl">Expiry</span><span class="det-val">09 / 28</span></div>
      <div class="det-row"><span class="det-lbl">Credit Limit</span><span class="det-val" style="color:var(--blue)">${o.amt}</span></div>
    </div>`;
}

let cardVis = false, cvvVis = false;
function toggleCardNum() {
  cardVis = !cardVis;
  const el = $('cdNum'), btn = el.nextElementSibling;
  el.textContent = cardVis ? '4821 0043 8812 4821' : '•••• •••• •••• 4821';
  btn.textContent = cardVis ? 'Hide' : 'Show';
  if ($('vcNum')) $('vcNum').textContent = cardVis ? '4821 0043 8812 4821' : '•••• •••• •••• 4821';
}
function toggleCVV() {
  cvvVis = !cvvVis;
  const el = $('cdCvv'), btn = el.nextElementSibling;
  el.textContent = cvvVis ? '847' : '•••';
  btn.textContent = cvvVis ? 'Hide' : 'Show';
}

// ── Credit Flow ──
async function startFlow() {
  if (busy) return;
  busy = true; flowState = 'greeted';

  showTyping(); await sleep(1100); rmTyping();
  const tgName = tg?.initDataUnsafe?.user?.first_name || 'there';
  let r = addBubble('inc', `👋 Hi ${tgName}! I'm your PayPal assistant.<br>What can I help you with today?`);
  addTs(r, 'inc');
  await sleep(300);
  showTopicMenu();
  busy = false;
}

function showTopicMenu() {
  const row = makeRow('inc');
  const bbl = document.createElement('div'); bbl.className = 'bbl bbl-wide';
  bbl.innerHTML = `<div class="topic-grid">
    <div class="topic-btn" onclick="pickTopic('credit')"><span class="tb-icon">💳</span><span class="tb-lbl">Apply for Credit</span><span class="tb-sub">See personalised offers</span></div>
    <div class="topic-btn" onclick="pickTopic('balance')"><span class="tb-icon">💰</span><span class="tb-lbl">Check Balance</span><span class="tb-sub">Balance, due date, limits</span></div>
    <div class="topic-btn" onclick="pickTopic('rewards')"><span class="tb-icon">🎁</span><span class="tb-lbl">Rewards</span><span class="tb-sub">Cashback & points</span></div>
    <div class="topic-btn" onclick="pickTopic('support')"><span class="tb-icon">🙋</span><span class="tb-lbl">Support</span><span class="tb-sub">Contact & help</span></div>
  </div>`;
  row.appendChild(bbl);
  requestAnimationFrame(() => requestAnimationFrame(() => { row.classList.add('show'); scroll(); }));
}

async function pickTopic(topic) {
  if (busy) return;
  document.querySelectorAll('.topic-btn').forEach(b => { b.style.opacity = '0.45'; b.style.pointerEvents = 'none'; });
  if (topic === 'credit') await startCredit();
  else if (topic === 'balance') await startBalance();
  else if (topic === 'rewards') await startRewards();
  else if (topic === 'support') await startSupport();
}

async function startCredit() {
  busy = true;
  let r = addBubble('out', 'Apply for Credit'); addTs(r, 'out');
  await sleep(400);
  showTyping(); await sleep(1000); rmTyping();
  addBubble('inc', 'Great choice! Our NBA Model will match you to the best credit product based on your PayPal profile.<br><br>First, let me securely connect your PayPal account. This uses OAuth — I never see your password. 🔒');
  await sleep(300);

  // Auth card
  const row = makeRow('inc');
  const bbl = document.createElement('div'); bbl.className = 'bbl';
  bbl.innerHTML = `<div class="auth-card">
    <div class="ac-hd"><svg viewBox="0 0 24 24" fill="none" width="16" height="16"><path d="M19.5 6.5C19.5 9.54 17.04 12 14 12H9.5L8 19H4.5L7 6.5H14Z" fill="#60CDFF"/><path d="M20 4C20 7.04 17.54 9.5 14.5 9.5H10L8.5 16.5H5L7.5 4H14.5Z" fill="white" opacity="0.3"/></svg><span>Connect PayPal</span></div>
    <div class="ac-body">
      <div class="ac-desc">Sign in to unlock personalised credit offers.</div>
      <button class="ac-btn" onclick="showLogin()">🔐 Connect with PayPal</button>
    </div>
  </div>`;
  row.appendChild(bbl);
  requestAnimationFrame(() => requestAnimationFrame(() => { row.classList.add('show'); scroll(); }));
  busy = false;
}

async function runScoring() {
  busy = true;
  showTyping(); await sleep(1400); rmTyping();
  addBubble('inc', '⚡ Scoring your profile with the NBA Model...');
  await sleep(1800);
  showTyping(); await sleep(800); rmTyping();

  let r = addBubble('inc', '🎯 Great news — the NBA Model matched you to <b>3 personalised offers</b>.<br>Tap one to learn more:');
  addTs(r, 'inc');
  await sleep(250);

  const ofrow = makeRow('inc');
  const ofbbl = document.createElement('div'); ofbbl.className = 'bbl bbl-wide';
  ofbbl.innerHTML = `<div class="offers-wrap">${OFFERS.map((o, i) => `
    <div class="oc" onclick="handleOffer(${i})"><span class="oc-arrow">›</span>
      <div class="oc-tag">${o.tag}</div><div class="oc-name">${o.name}</div>
      <div class="oc-amt">${o.amt}</div><div class="oc-detail">${o.detail}</div>
    </div>`).join('')}</div>`;
  ofrow.appendChild(ofbbl);
  requestAnimationFrame(() => requestAnimationFrame(() => { ofrow.classList.add('show'); scroll(); }));
  flowState = 'offers'; busy = false;
}

async function handleOffer(i) {
  if (busy || flowState !== 'offers') return;
  busy = true; chosenOffer = i;
  document.querySelectorAll('.oc').forEach((c, j) => { c.classList.toggle('picked', j === i); c.classList.add('disabled'); });
  const o = OFFERS[i];
  await sleep(150);
  let r = addBubble('out', `${o.name} 👍`); addTs(r, 'out');
  await sleep(450);
  showTyping(); await sleep(900); rmTyping();
  addBubble('inc', `<b>${o.name}</b><br><br>💳 Credit limit: <b>${o.amt}</b><br>📋 ${o.detail}<br><br>Would you like to go ahead?`);
  await sleep(300);

  const cRow = makeRow('inc');
  const cBbl = document.createElement('div'); cBbl.className = 'bbl';
  cBbl.innerHTML = `<div class="chips">
    <div class="chip" onclick="proceedApply()">Yes, apply now</div>
    <div class="chip" onclick="askMore()">Tell me more</div>
    <div class="chip" onclick="goBackOffers()">See other offers</div>
  </div>`;
  cRow.appendChild(cBbl);
  requestAnimationFrame(() => requestAnimationFrame(() => { cRow.classList.add('show'); scroll(); }));
  flowState = 'reviewing'; busy = false;
}

async function proceedApply() {
  if (busy) return; busy = true;
  document.querySelectorAll('.chip').forEach(c => { c.style.opacity = '0.4'; c.style.pointerEvents = 'none'; });
  const o = OFFERS[chosenOffer];
  let r = addBubble('out', 'Yes, apply now'); addTs(r, 'out');
  await sleep(400);
  showTyping(); await sleep(800); rmTyping();
  addBubble('inc', '✨ Here\'s your application summary. Review and tap Submit:');
  await sleep(250);

  const crow = makeRow('inc');
  const cbbl = document.createElement('div'); cbbl.className = 'bbl';
  cbbl.innerHTML = `<div class="confirm-card">
    <div class="cc-hd"><div class="cc-tick">✓</div><div class="cc-title">Application Ready</div></div>
    <div class="cc-rows">
      <div class="cc-row"><span class="l">Product</span><span class="v">${o.name}</span></div>
      <div class="cc-row"><span class="l">Limit</span><span class="v">${o.amt}</span></div>
      <div class="cc-row"><span class="l">Applicant</span><span class="v">${userName || 'User'}</span></div>
      <div class="cc-row"><span class="l">Via</span><span class="v">Telegram</span></div>
      <div class="cc-row"><span class="l">Decision</span><span class="v hi">Instant · ~3s</span></div>
    </div>
    <button class="cc-submit" id="ccBtn" onclick="handleSubmit()">Submit Application →</button>
  </div>`;
  crow.appendChild(cbbl);
  requestAnimationFrame(() => requestAnimationFrame(() => { crow.classList.add('show'); scroll(); }));
  flowState = 'confirm'; busy = false;
}

async function handleSubmit() {
  if (busy || flowState !== 'confirm') return;
  busy = true;
  const btn = $('ccBtn');
  btn.textContent = 'Processing...'; btn.disabled = true;
  await sleep(1600);
  btn.textContent = '✓ Submitted!'; btn.classList.add('done');

  const o = OFFERS[chosenOffer];
  showTyping(); await sleep(1200); rmTyping();
  let r = addBubble('inc', `🎊 <b>Approved, ${userName || 'User'}!</b><br>Your <b>${o.name}</b> is active. Credit limit: <b>${o.amt}</b>.<br>Decision time: 3.1 seconds.`);
  addTs(r, 'inc');
  await sleep(600);
  showTyping(); await sleep(700); rmTyping();
  addBubble('inc', '📲 All done inside Telegram — no app downloads, no redirects. That\'s Agentic Commerce.');
  await sleep(400);

  // Post-approval menu
  const chipRow = makeRow('inc');
  const chipBbl = document.createElement('div'); chipBbl.className = 'bbl bbl-wide';
  chipBbl.innerHTML = `<div style="font-size:11px;color:var(--dim);margin-bottom:8px">What would you like to do next?</div>
    <div class="topic-grid">
      <div class="topic-btn" onclick="openScreen('statement')"><span class="tb-icon">📋</span><span class="tb-lbl">View Statement</span><span class="tb-sub">Transactions & balance</span></div>
      <div class="topic-btn" onclick="openScreen('card')"><span class="tb-icon">🃏</span><span class="tb-lbl">Manage Card</span><span class="tb-sub">Controls & settings</span></div>
      <div class="topic-btn" onclick="startBalance()"><span class="tb-icon">💰</span><span class="tb-lbl">Check Balance</span><span class="tb-sub">Balance & due date</span></div>
      <div class="topic-btn" onclick="startRewards()"><span class="tb-icon">🎁</span><span class="tb-lbl">View Rewards</span><span class="tb-sub">Cashback & points</span></div>
    </div>`;
  chipRow.appendChild(chipBbl);
  requestAnimationFrame(() => requestAnimationFrame(() => { chipRow.classList.add('show'); scroll(); }));
  flowState = 'done'; busy = false;

  if (tg) tg.sendData(JSON.stringify({ action: 'approved', product: o.name, limit: o.amt }));
}

async function askMore() {
  if (busy) return; busy = true;
  document.querySelectorAll('.chip').forEach(c => { c.style.opacity = '0.4'; c.style.pointerEvents = 'none'; });
  const o = OFFERS[chosenOffer];
  let r = addBubble('out', 'Tell me more'); addTs(r, 'out');
  await sleep(300);
  showTyping(); await sleep(1000); rmTyping();
  addBubble('inc', `Here's what to know about <b>${o.name}</b>:<br><br>✅ <b>Instant decision</b> — know in under 4 seconds<br>🔒 <b>No hard credit pull</b> to check eligibility<br>📱 <b>Digital-first</b> — manage entirely in PayPal<br>🛡 <b>Buyer Protection</b> included<br>💸 <b>${o.detail}</b><br><br>Ready to proceed?`);
  await sleep(250);
  const cRow = makeRow('inc');
  const cBbl = document.createElement('div'); cBbl.className = 'bbl';
  cBbl.innerHTML = `<div class="chips"><div class="chip" onclick="proceedApply()">Yes, apply now</div><div class="chip" onclick="goBackOffers()">See other offers</div></div>`;
  cRow.appendChild(cBbl);
  requestAnimationFrame(() => requestAnimationFrame(() => { cRow.classList.add('show'); scroll(); }));
  busy = false;
}

async function goBackOffers() {
  if (busy) return; busy = true;
  chosenOffer = null;
  document.querySelectorAll('.chip').forEach(c => { c.style.opacity = '0.4'; c.style.pointerEvents = 'none'; });
  let r = addBubble('out', 'See other offers'); addTs(r, 'out');
  await sleep(400);
  showTyping(); await sleep(700); rmTyping();
  addBubble('inc', 'Of course! Here are all three options again:');
  await sleep(250);
  const ofrow = makeRow('inc');
  const ofbbl = document.createElement('div'); ofbbl.className = 'bbl bbl-wide';
  ofbbl.innerHTML = `<div class="offers-wrap">${OFFERS.map((o, i) => `
    <div class="oc" onclick="handleOffer(${i})"><span class="oc-arrow">›</span>
      <div class="oc-tag">${o.tag}</div><div class="oc-name">${o.name}</div>
      <div class="oc-amt">${o.amt}</div><div class="oc-detail">${o.detail}</div>
    </div>`).join('')}</div>`;
  ofrow.appendChild(ofbbl);
  requestAnimationFrame(() => requestAnimationFrame(() => { ofrow.classList.add('show'); scroll(); }));
  flowState = 'offers'; busy = false;
}

async function startBalance() {
  busy = true;
  document.querySelectorAll('.topic-btn').forEach(b => { b.style.opacity = '0.45'; b.style.pointerEvents = 'none'; });
  let r = addBubble('out', 'Check Balance'); addTs(r, 'out');
  await sleep(300);
  showTyping(); await sleep(900); rmTyping();
  const o = OFFERS[chosenOffer ?? 0];
  const lim = parseFloat(o.amt.replace(/[^0-9.]/g, '')), used = 847.23;
  addBubble('inc', `<b>Your Account Summary</b><br><br>💳 <b>Current Balance:</b> $${used.toFixed(2)}<br>✅ <b>Available Credit:</b> $${(lim-used).toFixed(2)}<br>📅 <b>Payment Due:</b> Apr 15, 2026<br>💵 <b>Minimum Payment:</b> $25.00<br>📊 <b>Utilisation:</b> ${Math.round(used/lim*100)}% of ${o.amt}`);
  await sleep(300);
  const cRow = makeRow('inc');
  const cBbl = document.createElement('div'); cBbl.className = 'bbl';
  cBbl.innerHTML = `<div class="chips"><div class="chip" onclick="openScreen('statement')">📋 View Statement</div><div class="chip" onclick="openScreen('card')">🃏 Manage Card</div></div>`;
  cRow.appendChild(cBbl);
  requestAnimationFrame(() => requestAnimationFrame(() => { cRow.classList.add('show'); scroll(); }));
  busy = false;
}

async function startRewards() {
  busy = true;
  document.querySelectorAll('.topic-btn,.chip').forEach(b => { b.style.opacity = '0.45'; b.style.pointerEvents = 'none'; });
  let r = addBubble('out', 'Rewards'); addTs(r, 'out');
  await sleep(300);
  showTyping(); await sleep(950); rmTyping();
  addBubble('inc', `<b>Your Rewards Summary 🎁</b><br><br>💳 <b>Card:</b> ${OFFERS[chosenOffer??0].name}<br>💵 <b>Total Cashback:</b> $114.20<br>📅 <b>This Month:</b> $12.80<br>⭐ <b>Points:</b> 42,180<br>🎯 <b>Next Milestone:</b> $57.90 to reach $100`);
  busy = false;
}

async function startSupport() {
  busy = true;
  document.querySelectorAll('.topic-btn').forEach(b => { b.style.opacity = '0.45'; b.style.pointerEvents = 'none'; });
  let r = addBubble('out', 'Support'); addTs(r, 'out');
  await sleep(300);
  showTyping(); await sleep(800); rmTyping();
  addBubble('inc', '<b>How can we help?</b>');
  await sleep(200);
  const cRow = makeRow('inc');
  const cBbl = document.createElement('div'); cBbl.className = 'bbl';
  cBbl.innerHTML = `<div class="chips">
    <div class="chip" onclick="supportAction('call')">📞 Call PayPal</div>
    <div class="chip" onclick="supportAction('chat')">💬 Live Chat</div>
    <div class="chip" onclick="supportAction('dispute')">⚠️ Dispute</div>
    <div class="chip" onclick="supportAction('lost')">🔒 Lost Card</div>
  </div>`;
  cRow.appendChild(cBbl);
  requestAnimationFrame(() => requestAnimationFrame(() => { cRow.classList.add('show'); scroll(); }));
  busy = false;
}

async function supportAction(type) {
  document.querySelectorAll('.chip').forEach(c => { c.style.opacity = '0.4'; c.style.pointerEvents = 'none'; });
  const msgs = {
    call: '📞 <b>Call PayPal</b><br><br>1-888-221-1161<br>Mon–Fri 6am–6pm PT',
    chat: '💬 <b>Live Chat</b><br><br>Visit: paypal.com/us/smarthelp/home',
    dispute: '⚠️ <b>Dispute a Charge</b><br><br>1. Go to Activity<br>2. Find the transaction<br>3. Tap \'Report a Problem\'',
    lost: '🔒 <b>Lost Card</b><br><br>Your card has been frozen for safety.<br>Replacement in 3-5 business days.',
  };
  addBubble('inc', msgs[type]);
}

// ── Free text ──
async function doSend() {
  const inp = $('inpBox');
  const text = inp.value.trim();
  if (!text || busy) return;
  inp.value = '';
  let r = addBubble('out', text); addTs(r, 'out');

  if (flowState === 'idle') { await startFlow(); return; }

  // Try LLM for unmatched text
  busy = true;
  showTyping();
  try {
    const res = await fetch(`${API}/test-llm?q=${encodeURIComponent(text)}`);
    const data = await res.json();
    rmTyping();
    if (data.response) {
      addBubble('inc', data.response);
    } else {
      addBubble('inc', 'I can help with credit products, balance, rewards, and more. Tap a menu option or ask me anything!');
    }
  } catch (e) {
    rmTyping();
    addBubble('inc', 'Something went wrong. Please try again.');
  }
  busy = false;
}

// ── Auto-start ──
window.addEventListener('load', () => {
  if (openedForLogin) {
    // Opened from bot chat for login only — hide chat, show login directly
    document.querySelector('.chat-hd').style.display = 'none';
    document.querySelector('.chat-bg').style.display = 'none';
    document.querySelector('.chat-inp').style.display = 'none';
    $('loginOverlay').classList.add('show');
  } else {
    // Normal Mini App — start chat flow
    setTimeout(startFlow, 500);
  }
});
