'use strict';
const $ = id => document.getElementById(id);
let status, conversation = null, activeRole = 'desk-lead', busy = false, marketRequest = 0;
const roleInfo = {
  'desk-lead': ['▤', 'Your point of contact on the floor'],
  'market-analyst': ['◴', 'Prices, funding, liquidity, and sourced market facts'],
  'research-analyst': ['⌕', 'Research methods and evidence gaps; no live web tool'],
  'strategist': ['⌘', 'Turn your own hypothesis into explicit test rules'],
  'risk-manager': ['◇', 'Challenge assumptions and estimate stressed stop costs'],
  'execution-trader': ['↗', 'Execution planning only; exchange writes are disabled'],
  'trade-reviewer': ['▧', 'Review the process and the outcome separately']
};
function node(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}
async function api(path, body) {
  const options = body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Desk-Token': status.csrf_token}, body: JSON.stringify(body)};
  let response;
  try { response = await fetch(path, options); } catch { throw new Error('The local app is unreachable. Start the Python server and reload this page.'); }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'The request failed.');
  return result;
}
function errorAt(id, message = '') {
  $(id).textContent = message;
  $(id).classList.toggle('hidden', !message);
}
function inlineText(parent, text) {
  // Render emphasis without interpreting model-generated HTML or URLs.
  for (const [i, part] of text.split(/\*\*(.+?)\*\*/g).entries()) {
    parent.append(i % 2 ? node('strong', '', part) : document.createTextNode(part));
  }
}
function renderText(parent, text) {
  let list = null;
  for (const line of text.split('\n')) {
    const item = line.match(/^\s*(?:[-*]|\d+\.)\s+(.+)/);
    if (item) {
      if (!list) { list = node('ul'); parent.append(list); }
      const li = node('li'); inlineText(li, item[1]); list.append(li);
    } else {
      list = null;
      if (!line.trim()) continue;
      const heading = line.match(/^#{1,4}\s+(.+)/);
      const block = node(heading ? 'h3' : 'p');
      inlineText(block, heading ? heading[1] : line); parent.append(block);
    }
  }
}
function showWelcome() {
  const box = node('div', 'welcome');
  box.append(node('div', 'welcome-mark', '✳'), node('h3', '', 'A clear view starts here.'));
  box.append(node('p', '', 'Your OpenAI-powered desk brings market data and a disciplined research process into one conversation.'));
  const suggestions = node('div', 'suggestions');
  for (const [title, note, prompt] of [
    ['Brief me on ETH', 'Funding, depth & market context', 'Brief me on ETH using a fresh market snapshot. Separate facts from interpretation.'],
    ['Check market liquidity', 'Look beneath the headline price', 'Read the current ETH book. Explain the measured depth and any coverage limitations.'],
    ['Understand risk sizing', 'Start with the assumptions', 'Explain what information you need from me to estimate a stressed stop cost.'],
    ['Explore the workflow', 'Meet your research desk', 'Explain how the seven desk roles work in this local research app, and which capabilities are unavailable.']]) {
    const button = node('button', 'suggestion', title); button.type = 'button'; button.append(node('span', '', note));
    button.addEventListener('click', () => { $('message').value = prompt; $('message').focus(); });
    suggestions.append(button);
  }
  box.append(suggestions); $('messages').replaceChildren(box);
}
function appendMessage(row) {
  const item = node('article', `message ${row.role}`);
  const meta = node('div', 'message-meta');
  meta.append(node('span', 'avatar', row.role === 'user' ? 'Y' : roleInfo[row.seat || activeRole][0]),
    node('span', '', row.role === 'user' ? 'You' : status.roles[row.seat || activeRole]));
  const time = node('time', '', new Date(row.created_at || Date.now()).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'}));
  meta.append(time);
  const body = node('div', 'message-body'); renderText(body, row.content);
  item.append(meta, body);
  const details = row.details || {};
  if (details.traces?.length) {
    const evidence = node('details'); evidence.append(node('summary', '', `Inspect evidence · ${details.traces.length} tool calls`));
    evidence.append(node('pre', '', JSON.stringify(details.traces, null, 2))); item.append(evidence);
  }
  if (details.usage) item.append(node('div', 'usage', `${details.model} · ${details.usage.input_tokens.toLocaleString()} input / ${details.usage.output_tokens.toLocaleString()} output tokens`));
  $('messages').append(item);
}
function setRole(role) {
  activeRole = role;
  document.querySelectorAll('.role-button').forEach(el => el.classList.toggle('active', el.dataset.role === role));
  $('chat-role').textContent = status.roles[role]; $('composer-role').textContent = status.roles[role];
  $('role-description').textContent = roleInfo[role][1];
}
async function refreshStatus() {
  status = await api('/api/status');
  $('provider-label').textContent = status.configured ? 'OpenAI connected' : 'Connect OpenAI';
  $('provider-dot').classList.toggle('ready', status.configured);
  $('composer-model').textContent = status.model;
  $('key-state').textContent = status.configured ? 'A key is configured. Leave blank to keep it.' : 'No key configured. Market snapshots work without one.';
  $('model').value = status.model; $('storage').textContent = `Local conversations: ${status.storage}`;
}
async function refreshHistory() {
  const rows = await api('/api/conversations'); $('history').replaceChildren();
  if (!rows.length) $('history').append(node('div', 'empty-history', 'Your conversations appear here.'));
  for (const row of rows) {
    const button = node('button', `history-button${row.id === conversation ? ' active' : ''}`, row.title);
    button.disabled = busy; button.title = row.title;
    button.addEventListener('click', async () => {
      try {
        const messages = await api('/api/messages?id=' + encodeURIComponent(row.id));
        conversation = row.id; errorAt('chat-error'); $('messages').replaceChildren();
        if (!messages.length) showWelcome(); else messages.forEach(appendMessage);
        if (messages.length) setRole(messages.at(-1).seat);
        await refreshHistory(); $('messages').scrollTop = $('messages').scrollHeight;
      } catch (error) { errorAt('chat-error', error.message); }
    }); $('history').append(button);
  }
}
function setBusy(value) {
  busy = value;
  document.querySelectorAll('.role-button, .history-button').forEach(el => el.disabled = value);
  $('new-chat').disabled = value; $('send').disabled = value; $('message').disabled = value;
  $('send').firstChild.textContent = value ? 'Working ' : 'Send ';
}
function money(value, compact = false) {
  if (value === undefined || value === null || !Number.isFinite(Number(value))) return '—';
  return new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD', notation: compact ? 'compact' : 'standard', maximumFractionDigits: 2}).format(Number(value));
}
function clearMarket(message) {
  ['price','funding','oi','spread','mark','oracle','volume','change'].forEach(id => $(id).textContent = '—');
  $('depth').replaceChildren(node('div', 'empty-depth', 'Market data unavailable.'));
  $('data-status').classList.remove('ready'); $('observed').textContent = message;
  $('raw-market').textContent = 'No current snapshot available.';
}
async function loadMarket() {
  const request = ++marketRequest, coin = $('coin').value.trim();
  $('refresh-market').disabled = true; errorAt('market-error');
  clearMarket('Fetching a fresh snapshot…'); $('market-name').textContent = coin + '-PERP';
  try {
    const data = await api('/api/market?coin=' + encodeURIComponent(coin));
    if (request !== marketRequest) return;
    $('market-name').textContent = data.market; $('price').textContent = money(data.prices.book_mid);
    const change = Number(data.prices.change_24h_pct);
    $('change').textContent = `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`; $('change').classList.toggle('negative', change < 0);
    $('funding').textContent = `${Number(data.funding.hourly_pct) >= 0 ? '+' : ''}${Number(data.funding.hourly_pct).toFixed(5)}%`;
    $('oi').textContent = money(data.activity.open_interest_usd, true);
    $('spread').textContent = Number(data.book.spread_bps).toFixed(3);
    $('mark').textContent = money(data.prices.mark); $('oracle').textContent = money(data.prices.oracle);
    $('volume').textContent = money(data.activity.volume_24h_usd, true);
    const rows = Object.entries(data.book.depth), max = Math.max(...rows.flatMap(([,r]) => [Number(r.bid_usd), Number(r.ask_usd)]), 1);
    $('depth').replaceChildren();
    for (const [band, values] of rows) {
      const row = node('div', 'depth-row'), top = node('div', 'depth-row-top');
      const bid = `${values.bid_complete ? '' : '≥ '}${money(values.bid_usd, true)}`;
      const ask = `${values.ask_complete ? '' : '≥ '}${money(values.ask_usd, true)}`;
      top.append(node('span', '', `${band} bps`), node('span', '', `${bid} / ${ask}`));
      const bars = node('div', 'depth-bars');
      // SVG width attributes avoid inline CSS under the app's strict CSP.
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', '0 0 200 6'); svg.setAttribute('width', '100%'); svg.setAttribute('height', '6'); svg.setAttribute('aria-hidden', 'true');
      for (const [side, color] of [['bid', '#bfd896'], ['ask', '#e9c2ad']]) {
        const width = Math.max(1, Number(values[side + '_usd']) / max * 97);
        const rect = document.createElementNS(svg.namespaceURI, 'rect');
        for (const [attr, val] of Object.entries({x: side === 'bid' ? 98 - width : 102, y: 0, width, height: 6, rx: 2, fill: color})) rect.setAttribute(attr, val);
        svg.append(rect);
      }
      bars.append(svg); row.append(top, bars); $('depth').append(row);
    }
    $('data-status').classList.add('ready');
    $('observed').textContent = `${data.source.observed_at.replace('T', ' ').replace(/\.\d+\+00:00$/, ' UTC').replace('Z', ' UTC')}`;
    $('raw-market').textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    if (request !== marketRequest) return;
    clearMarket('Snapshot unavailable'); errorAt('market-error', error.message);
  } finally { if (request === marketRequest) $('refresh-market').disabled = false; }
}
$('chat-form').addEventListener('submit', async event => {
  event.preventDefault(); if (busy) return;
  const message = $('message').value.trim(); if (!message) return;
  if (!status.configured) { $('settings').showModal(); $('api-key').focus(); return; }
  errorAt('chat-error'); setBusy(true);
  if ($('messages').querySelector('.welcome')) $('messages').replaceChildren();
  const userRow = {role: 'user', content: message, seat: activeRole}; appendMessage(userRow);
  const optimistic = $('messages').lastElementChild;
  const thinking = node('div', 'thinking', 'The desk is checking your request. Tool calls and specialist passes can take a moment.');
  $('messages').append(thinking); $('messages').scrollTop = $('messages').scrollHeight;
  try {
    if (!conversation) conversation = (await api('/api/conversations', {})).id;
    const answer = await api('/api/chat', {conversation_id: conversation, message, role: activeRole});
    thinking.remove(); appendMessage({role: 'assistant', seat: activeRole, content: answer.content, details: answer});
    $('message').value = ''; await refreshHistory();
  } catch (error) {
    thinking.remove(); optimistic.remove(); errorAt('chat-error', error.message);
  } finally {
    setBusy(false); $('message').focus(); $('messages').scrollTop = $('messages').scrollHeight;
  }
});
$('message').addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); $('chat-form').requestSubmit(); } });
$('new-chat').addEventListener('click', () => { conversation = null; errorAt('chat-error'); showWelcome(); refreshHistory().catch(e => errorAt('chat-error', e.message)); $('message').focus(); });
$('market-form').addEventListener('submit', event => { event.preventDefault(); loadMarket(); });
$('settings-open').addEventListener('click', () => $('settings').showModal());
$('settings-close').addEventListener('click', () => { $('api-key').value = ''; $('settings').close(); });
$('settings').addEventListener('close', () => { $('api-key').value = ''; errorAt('settings-error'); });
$('settings-form').addEventListener('submit', async event => {
  event.preventDefault(); $('save-settings').disabled = true; errorAt('settings-error');
  try { await api('/api/settings', {api_key: $('api-key').value.trim(), model: $('model').value.trim()}); $('api-key').value = ''; await refreshStatus(); $('settings').close(); }
  catch (error) { errorAt('settings-error', error.message); }
  finally { $('save-settings').disabled = false; }
});
$('disconnect').addEventListener('click', async () => {
  try { await api('/api/settings', {clear_key: true, model: $('model').value.trim()}); $('api-key').value = ''; await refreshStatus(); }
  catch (error) { errorAt('settings-error', error.message); }
});
async function init() {
  $('today').textContent = new Date().toLocaleDateString('en-CA', {month: 'short', day: 'numeric', year: 'numeric'});
  await refreshStatus();
  for (const [role, title] of Object.entries(status.roles)) {
    const button = node('button', 'role-button'); button.dataset.role = role;
    button.append(node('span', 'role-icon', roleInfo[role][0]), document.createTextNode(title));
    button.addEventListener('click', () => setRole(role)); $('roles').append(button);
  }
  setRole(activeRole); showWelcome(); await refreshHistory(); await loadMarket();
}
init().catch(error => errorAt('chat-error', error.message));
