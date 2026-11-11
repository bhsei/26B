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
  const activeTiles = [...document.querySelectorAll('.tile-btn.active')].map(btn => btn.dataset.symbol);
  const value = {
    scene_hint: el('scene').value.trim(),
    intent_text: el('intent').value.trim(),
    selected_symbols: activeTiles,
    language: 'en'
  };
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
  const resultData = await api(url, options);
  render(resultData);
  document.getElementById('tab-context').classList.remove('active');
  document.getElementById('tab-speak').classList.add('active');
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

document.querySelectorAll('.tile-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    btn.classList.toggle('active');
    
    current = null;
    el('results').replaceChildren();
    lock(false);
    if ('speechSynthesis' in window) speechSynthesis.cancel();
    status('Tiles changed. Generate new suggestions.');
  });
});

const photoInput = el('photo');
const btnCamera = el('btn-camera');
const btnGallery = el('btn-gallery');
const dropZone = el('drop-zone');
const photoPreview = el('photo-preview');
const previewImg = el('preview-img');
const removePhotoBtn = el('remove-photo');

btnCamera.addEventListener('click', () => {
  photoInput.setAttribute('capture', 'environment');
  photoInput.click();
});

btnGallery.addEventListener('click', () => {
  photoInput.removeAttribute('capture');
  photoInput.click();
});

dropZone.addEventListener('click', () => {
  photoInput.removeAttribute('capture');
  photoInput.click();
});

['dragenter', 'dragover'].forEach(eventName => {
  dropZone.addEventListener(eventName, (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });
});

['dragleave', 'drop'].forEach(eventName => {
  dropZone.addEventListener(eventName, (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
  });
});

dropZone.addEventListener('drop', (e) => {
  const dt = e.dataTransfer;
  const files = dt.files;
  if (files && files.length > 0) {
    photoInput.files = files;
    handleFileSelect();
  }
});

photoInput.addEventListener('change', handleFileSelect);

function handleFileSelect() {
  const file = photoInput.files[0];
  if (file) {
    const reader = new FileReader();
    reader.onload = (e) => {
      previewImg.src = e.target.result;
      photoPreview.style.display = 'flex';
    };
    reader.readAsDataURL(file);
  }
}

removePhotoBtn.addEventListener('click', () => {
  photoInput.value = '';
  photoPreview.style.display = 'none';
  previewImg.src = '';
});

const contextRules = [
  {
    keywords: ["café", "cafe", "coffee shop", "starbucks", "coffee", "pay"],
    tiles: [
      { symbol: "water", label: "Water", png: "/static/symbols/water.png" },
      { symbol: "coffee", label: "Coffee", png: "/static/symbols/coffee.png" },
      { symbol: "sugar", label: "Sugar", png: "/static/symbols/sugar.png" },
      { symbol: "milk", label: "Milk", png: "/static/symbols/milk.png" },
      { symbol: "hot", label: "Hot", png: "/static/symbols/hot.png"},
      { symbol: "cold", label: "Cold", png: "/static/symbols/cold.png"},
      { symbol: "take_away", label: "Take away", png: "/static/symbols/takeaway.png"},
      { symbol: "eat_in", label: "Eat in", png: "/static/symbols/eatin.png"}
    ]
  },
  {
    keywords: ["post office", "poste", "mail", "package", "letter", "ship"],
    tiles: [
      { symbol: "parcel", label: "Parcel", png: "/static/symbols/parcel.png" },
      { symbol: "letter", label: "Letter", png: "/static/symbols/letter.png" },
      { symbol: "retrieve", label: "Retrieve", png: "/static/symbols/retreive.png" },
      { symbol: "deliver", label: "Deliver", png: "/static/symbols/deliver.png" }
    ]
  },
  {
    keywords: ["restaurant", "resto", "diner", "lunch", "eat", "breakfast", "brunch", "bill", "pay"],
    tiles: [
      { symbol: "order", label: "Order", png: "/static/symbols/order.png" },
      { symbol: "bill", label: "Bill", png: "/static/symbols/bill.png" },
      { symbol: "pay", label: "Pay", png: "/static/symbols/pay.png" },
      { symbol: "menus", label: "Menus", png: "/static/symbols/menu.png" },
      { symbol: "reservation", label: "Reservation", png: "/static/symbols/reservation.png" },
      { symbol: "drinks", label: "Drinks", png: "/static/symbols/drinks.png" },
      { symbol: "main courses", label: "Main courses", png: "/static/symbols/maincourses.png" }
    ]
  },
  {
    keywords: ["street", "outside", "direction", "location", "way", "subway", "bus", "find", "information", "stop", "hospital", "police"],
    tiles: [
      { symbol: "subway_station", label: "Subway station", png: "/static/symbols/subway.png" },
      { symbol: "bus_stop", label: "Bus stop", png: "/static/symbols/bus.png" },
      { symbol: "police_station", label: "Police station", png: "/static/symbols/police.png" },
      { symbol: "info_center", label: "Information center", png: "/static/symbols/infocenter.png" },
      { symbol: "city_center", label: "City center", png: "/static/symbols/citycenter.png" },
      { symbol: "hospital", label: "Hospital", png: "/static/symbols/hospital.png" }
    ]
  },
  {
    keywords: ["clothes", "shopping", "mall", "store", "outlet", "size", "shoes", "snickers", "price", "pricetag"],
    tiles: [
      { symbol: "item", label: "Item", png: "/static/symbols/item.png" },
      { symbol: "sizeup", label: "Size +", png: "/static/symbols/sizeup.png" },
      { symbol: "sizedown", label: "Size -", png: "/static/symbols/sizedown.png" },
      { symbol: "pricetag", label: "Pricetag", png: "/static/symbols/pricetag.png" },
      { symbol: "color", label: "Color", png: "/static/symbols/color.png" }
    ]
  }
];

const defaultTiles = [
  { symbol: "help", label: "Help", svg: '<line x1="12" y1="5" x2="12" y2="13" stroke-width="2.5" stroke-linecap="round"/><circle cx="12" cy="19" r="1.3" fill="currentColor"/>' }
];

function updateTiles() {
  const sceneValue = el('scene').value.trim().toLowerCase();
  const container = el('tiles-container');
  container.replaceChildren();

  // 1. On récupère toutes les règles qui correspondent aux mots-clés
  const matchedRules = contextRules.filter(rule => 
    rule.keywords.some(keyword => sceneValue.includes(keyword))
  );

  // 2. On fusionne toutes les tuiles correspondantes
  let tiles = [];
  if (matchedRules.length > 0) {
    matchedRules.forEach(rule => {
      tiles = tiles.concat(rule.tiles);
    });
  } else {
    tiles = defaultTiles;
  }

  // 3. Suppression propre des doublons (sans risque d'erreur)
  const uniqueTiles = [];
  const seenSymbols = new Set();
  tiles.forEach(t => {
    if (!seenSymbols.has(t.symbol)) {
      seenSymbols.add(t.symbol);
      uniqueTiles.push(t);
    }
  });

  // 4. Affichage des tuiles dans la grille
  uniqueTiles.forEach((t, index) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    const isActive = (index === 0 && t.symbol !== 'help') ? 'active' : '';
    btn.className = `tile-btn ${isActive}`;
    btn.dataset.symbol = t.symbol;

    const iconHtml = t.png 
        ? `<img src="${t.png}" alt="${t.label}" class="tile-img">`
        : `<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">${t.svg}</svg>`;

    btn.innerHTML = `
        ${iconHtml}
        <span>${t.label}</span>
    `;

    btn.addEventListener('click', () => {
      if (t.symbol === 'help') {
        el('help-modal').style.display = 'flex';
        return;
      }

      btn.classList.toggle('active');
      current = null;
      el('results').replaceChildren();
      lock(false);
      if ('speechSynthesis' in window) speechSynthesis.cancel();
      status('Tiles changed. Generate new suggestions.');
    });

    container.append(btn);
  });
}

document.addEventListener('DOMContentLoaded', updateTiles);

el('scene').addEventListener('input', () => {
  updateTiles();
});

el('close-modal-btn').addEventListener('click', () => {
  el('help-modal').style.display = 'none';
});

document.getElementById('back-to-context').addEventListener('click', () => {
  document.getElementById('tab-speak').classList.remove('active');
  document.getElementById('tab-context').classList.add('active');
});
