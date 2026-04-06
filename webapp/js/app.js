/* PayPal Credit Agent — Mini App Logic */

const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

const API = '/api';
let currentScreen = 'home';
let screenHistory = ['home'];
let selectedOffer = null;

// ── Screen Navigation ──
function showScreen(name) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById('screen-' + name).classList.add('active');
  currentScreen = name;
  screenHistory.push(name);

  const back = document.getElementById('nav-back');
  back.style.display = name === 'home' ? 'none' : 'block';

  const titles = {
    home: 'PayPal Credit', offers: 'Credit Offers', confirm: 'Confirm Application',
    approved: 'Approved!', statement: 'Statement', card: 'Manage Card', rewards: 'Rewards'
  };
  document.getElementById('nav-title').textContent = titles[name] || 'PayPal Credit';

  if (name === 'offers') loadOffers();
  if (name === 'statement') loadTransactions();
}

function goBack() {
  screenHistory.pop();
  const prev = screenHistory[screenHistory.length - 1] || 'home';
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById('screen-' + prev).classList.add('active');
  currentScreen = prev;
  document.getElementById('nav-back').style.display = prev === 'home' ? 'none' : 'block';
  const titles = {
    home: 'PayPal Credit', offers: 'Credit Offers', confirm: 'Confirm Application',
    statement: 'Statement', card: 'Manage Card', rewards: 'Rewards'
  };
  document.getElementById('nav-title').textContent = titles[prev] || 'PayPal Credit';
}

// ── Offers ──
async function loadOffers() {
  const res = await fetch(API + '/offers');
  const offers = await res.json();
  const list = document.getElementById('offers-list');
  list.innerHTML = offers.map((o, i) => `
    <div class="offer-card ${o.highlight ? 'highlight' : ''}" onclick="selectOffer(${i})">
      <div class="oc-tag">${o.tag}</div>
      <div class="oc-name">${o.name}</div>
      <div class="oc-amount">${o.amount}</div>
      <div class="oc-detail">${o.detail}</div>
      <div class="oc-score-bar"><div class="oc-score-fill" style="width:${o.score}%"></div></div>
      <div class="oc-score-label">Match: ${o.score}%</div>
    </div>
  `).join('');
}

function selectOffer(index) {
  selectedOffer = index;
  fetch(API + '/offers').then(r => r.json()).then(offers => {
    const o = offers[index];
    document.getElementById('confirm-card').innerHTML = `
      <div class="cc-header">
        <div class="cc-check">✓</div>
        <div class="cc-title">Application Ready</div>
      </div>
      <div class="cc-rows">
        <div class="cc-row"><span class="l">Product</span><span class="v">${o.name}</span></div>
        <div class="cc-row"><span class="l">Credit Limit</span><span class="v hi">${o.amount}</span></div>
        <div class="cc-row"><span class="l">Applicant</span><span class="v">Arun Sharma</span></div>
        <div class="cc-row"><span class="l">Channel</span><span class="v">Telegram</span></div>
        <div class="cc-row"><span class="l">Decision</span><span class="v hi">Instant · ~3s</span></div>
      </div>
      <div style="padding:0 16px 16px">
        <button class="btn-primary" onclick="submitApplication()">Submit Application →</button>
        <button class="btn-secondary" style="margin-top:8px" onclick="showScreen('offers')">← Back to Offers</button>
      </div>
    `;
    showScreen('confirm');
  });
}

async function submitApplication() {
  const res = await fetch(API + '/apply?offer_index=' + selectedOffer, { method: 'POST' });
  const result = await res.json();

  document.getElementById('approved-card').innerHTML = `
    <div class="ap-emoji">🎉</div>
    <div class="ap-title">Congratulations!</div>
    <div class="ap-sub">Your application has been approved</div>
    <div class="ap-grid">
      <div class="ap-cell"><div class="ap-label">Product</div><div class="ap-val">${result.product}</div></div>
      <div class="ap-cell"><div class="ap-label">Credit Limit</div><div class="ap-val">${result.limit}</div></div>
      <div class="ap-cell"><div class="ap-label">Decision Time</div><div class="ap-val">${(result.decision_ms / 1000).toFixed(1)}s</div></div>
      <div class="ap-cell"><div class="ap-label">Status</div><div class="ap-val">Active ✓</div></div>
    </div>
  `;
  showScreen('approved');

  if (tg) {
    tg.sendData(JSON.stringify({ action: 'approved', product: result.product, limit: result.limit }));
  }
}

// ── Transactions ──
async function loadTransactions() {
  const res = await fetch(API + '/transactions');
  const txns = await res.json();
  const list = document.getElementById('txn-list');
  list.innerHTML = txns.map(t => `
    <div class="txn-item">
      <div class="txn-icon">${t.icon}</div>
      <div class="txn-info">
        <div class="txn-name">${t.name}</div>
        <div class="txn-cat">${t.category}</div>
      </div>
      <div class="txn-right">
        <div class="txn-amt ${t.credit ? 'credit' : ''}">${t.amount}</div>
        <div class="txn-date">${t.date}</div>
      </div>
    </div>
  `).join('');
}

// ── Card toggles ──
let cardVisible = false;
let cvvVisible = false;

function toggleCard() {
  const el = document.getElementById('card-num');
  const btn = el.nextElementSibling;
  cardVisible = !cardVisible;
  el.textContent = cardVisible ? '4821 0043 8812 4821' : '•••• •••• •••• 4821';
  btn.textContent = cardVisible ? 'Hide' : 'Show';
}

function toggleCVV() {
  const el = document.getElementById('card-cvv');
  const btn = el.nextElementSibling;
  cvvVisible = !cvvVisible;
  el.textContent = cvvVisible ? '847' : '•••';
  btn.textContent = cvvVisible ? 'Hide' : 'Show';
}
