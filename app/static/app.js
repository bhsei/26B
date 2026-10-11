const el = id => document.getElementById(id);
let current = null;
let busy = false;
function status(message) { el('status').textContent = message; }
function selected() { return document.querySelector('input[name="sentence"]:checked'); }
function lock(value) {
  busy = value;
  el('context-form').querySelectorAll('input,button').forEach(node => node.disabled = value);
  document.querySelectorAll('input[name="sentence"]').forEach(node => node.disabled = value);
  el('speak').disabled = value || !selected();
  el('reject').disabled = value || !current || !current.suggestions.length;
}
async function api(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map(x => x.msg).join(' ') : data.detail;
    throw new Error(detail || 'Request failed.');
  }
  return data;
}
function payload(parent) {
  const value = {scene_hint: el('scene').value.trim(), intent_text: el('intent').value.trim(),
    selected_symbols: [...document.querySelectorAll('[name="symbol"]:checked')].map(x => x.value), language: 'en'};
  if (parent) value.parent_request_id = parent;
  return value;
}
function render(data) {
  current = data;
  el('results').replaceChildren();
  for (const suggestion of data.suggestions) {
    const label = document.createElement('label'); label.className = 'choice';
    const input = document.createElement('input'); input.type = 'radio';
    input.name = 'sentence'; input.value = suggestion.id;
    input.addEventListener('change', () => lock(busy));
    label.append(input, document.createTextNode(suggestion.text));
    el('results').append(label);
  }
  if (!data.suggestions.length) el('results').textContent = 'No new options. Change your input or start a fresh request.';
  status(data.notice || 'Choose a sentence. Nothing is spoken automatically.');
}
async function generate(parent = null) {
  const photo = el('photo').files[0];
  const value = payload(parent);
  if (!value.intent_text && !value.selected_symbols.length) throw new Error('Select a symbol or enter your intention.');
  let options, url = '/api/suggestions';
  if (photo) {
    if (photo.size > 5 * 1024 * 1024) throw new Error('Photo exceeds 5 MiB.');
    const form = new FormData(); form.append('payload', JSON.stringify(value)); form.append('image', photo);
    options = {method: 'POST', body: form}; url += '/image';
  } else options = {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(value)};
  render(await api(url, options));
}
async function saveFeedback(action, suggestionId = null) {
  return api(`/api/requests/${current.request_id}/feedback`, {method: 'PUT',
    headers: {'Content-Type':'application/json'}, body: JSON.stringify({action, suggestion_id:suggestionId})});
}
el('context-form').addEventListener('input', () => {
  current = null; el('results').replaceChildren(); lock(false);
  if ('speechSynthesis' in window) speechSynthesis.cancel();
  status('Inputs changed. Generate new suggestions.');
});
el('context-form').addEventListener('submit', async event => {
  event.preventDefault(); lock(true); status('Preparing suggestions…');
  try { await generate(); } catch (error) { status(error.message); } finally { lock(false); }
});
el('reject').addEventListener('click', async () => {
  lock(true); status('Looking for different options…');
  try { const parent = current.request_id; await saveFeedback('rejected'); await generate(parent); }
  catch (error) { status(error.message); } finally { lock(false); }
});
el('speak').addEventListener('click', async () => {
  const item = current?.suggestions.find(s => s.id === selected()?.value);
  if (!item) return;
  lock(true);
  try {
    await saveFeedback('accepted', item.id);
    if (!('speechSynthesis' in window)) { status('Choice saved. Speech is unavailable in this browser.'); return; }
    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(item.text); utterance.lang = 'en-US';
    utterance.onerror = () => status('Choice saved. Speech could not play; check your English voice settings.');
    utterance.onend = () => status('Choice saved. Finished speaking.');
    status('Choice saved. Speaking…'); speechSynthesis.speak(utterance);
  } catch (error) { status(error.message); } finally { lock(false); }
});
el('stop').addEventListener('click', () => {
  if ('speechSynthesis' in window) speechSynthesis.cancel();
  status('Speech stopped.');
});
