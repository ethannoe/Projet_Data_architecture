/**
 * Urban Data Explorer — app.js
 * Dashboard interactif : carte Leaflet + Chart.js
 * Données Gold embarquées (fallback si API indisponible)
 */

// ── Configuration ──────────────────────────────────────────────────────────
// En développement local : "http://localhost:8000"
// En production (après déploiement Render) : remplacer par l'URL Render réelle
// ex: "https://urban-data-explorer-api.onrender.com"
const API_BASE = ["localhost", "127.0.0.1", ""].includes(window.location.hostname)
  ? "http://localhost:8000"
  : "https://urban-data-explorer-api.onrender.com";
const ANNEES = [2021, 2022, 2023, 2024, 2025];

// Année de référence par indicateur (hors prix_m2 qui a un historique 2021-2025)
const INDICATOR_DATES = {
  logements_sociaux_pct: "Données 2022",
  revenu_median_uc:      "INSEE Filosofi 2020",
  crimes_pour_mille:     "Données 2022",
  densite_hab_km2:       "INSEE Recensement 2020",
  variation_pct:         "Variation 2024→2025",
};

// Centroides approximatifs des arrondissements parisiens (lat, lng)
const ARR_CENTROIDS = {
  1:  [48.8602, 2.3477],  2:  [48.8675, 2.3490],  3:  [48.8637, 2.3605],
  4:  [48.8534, 2.3526],  5:  [48.8462, 2.3510],  6:  [48.8497, 2.3327],
  7:  [48.8566, 2.3097],  8:  [48.8742, 2.3090],  9:  [48.8764, 2.3378],
  10: [48.8763, 2.3600],  11: [48.8596, 2.3793],  12: [48.8404, 2.3978],
  13: [48.8311, 2.3577],  14: [48.8321, 2.3253],  15: [48.8418, 2.2977],
  16: [48.8637, 2.2690],  17: [48.8843, 2.3143],  18: [48.8921, 2.3453],
  19: [48.8808, 2.3817],  20: [48.8643, 2.4001],
};

// ── Données Gold embarquées (FALLBACK) ────────────────────────────────────
// Ces données sont une copie statique de la couche Gold (DVF 2021-2025).
// Elles ne sont utilisées QUE si l'API backend est inaccessible (hors ligne,
// déploiement non encore effectué, timeout réseau).
// En conditions normales, loadGoldData() les écrase avec la réponse de l'API.
let GOLD_DATA = [
  // Source: DVF data.gouv.fr (2021-2025) · INSEE DGFiP · SSMSI 2025 · OpenData Paris
  { num:1,  nom:"1er arrondissement",  surnom:"Louvre – Palais-Royal",             prix_medians:{2021:13514,2022:13535,2023:13260,2024:12647,2025:12500}, logements_sociaux_pct:4.3,  nb_logements_sociaux:877,   revenu_median_uc:35030, population:15114,  superficie_km2:1.825,  densite_hab_km2:8282,  crimes_pour_mille:577.3, variation_pct:-1.2, repartition_pieces:{T1:30.2,T2:32.0,T3:19.5,T4:9.5,"T5+":8.8} },
  { num:2,  nom:"2ème arrondissement", surnom:"Bourse",                             prix_medians:{2021:12062,2022:12128,2023:11890,2024:11435,2025:11410}, logements_sociaux_pct:5.1,  nb_logements_sociaux:658,   revenu_median_uc:34050, population:19847,  superficie_km2:0.991,  densite_hab_km2:20027, crimes_pour_mille:232.3, variation_pct:-0.2, repartition_pieces:{T1:35.9,T2:35.5,T3:17.5,T4:7.7,"T5+":3.4} },
  { num:3,  nom:"3ème arrondissement", surnom:"Temple – Marais Nord",               prix_medians:{2021:12759,2022:12692,2023:12496,2024:11920,2025:12200}, logements_sociaux_pct:7.8,  nb_logements_sociaux:1336,  revenu_median_uc:34800, population:32179,  superficie_km2:1.171,  densite_hab_km2:27480, crimes_pour_mille:135.8, variation_pct:2.3,  repartition_pieces:{T1:31.3,T2:35.1,T3:19.1,T4:9.5,"T5+":5.0} },
  { num:4,  nom:"4ème arrondissement", surnom:"Hôtel-de-Ville – Île de la Cité",    prix_medians:{2021:13370,2022:13462,2023:13432,2024:12846,2025:13075}, logements_sociaux_pct:6.9,  nb_logements_sociaux:1677,  revenu_median_uc:33040, population:27332,  superficie_km2:1.601,  densite_hab_km2:17072, crimes_pour_mille:185.0, variation_pct:1.8,  repartition_pieces:{T1:28.6,T2:32.5,T3:20.4,T4:10.3,"T5+":8.2} },
  { num:5,  nom:"5ème arrondissement", surnom:"Panthéon – Quartier Latin",          prix_medians:{2021:12995,2022:13103,2023:12581,2024:11978,2025:12000}, logements_sociaux_pct:7.2,  nb_logements_sociaux:2194,  revenu_median_uc:35960, population:55252,  superficie_km2:2.539,  densite_hab_km2:21761, crimes_pour_mille:102.5, variation_pct:0.2,  repartition_pieces:{T1:32.0,T2:32.3,T3:19.3,T4:9.2,"T5+":7.1} },
  { num:6,  nom:"6ème arrondissement", surnom:"Luxembourg – Saint-Germain",         prix_medians:{2021:15492,2022:15458,2023:15369,2024:14935,2025:14583}, logements_sociaux_pct:3.2,  nb_logements_sociaux:920,   revenu_median_uc:41750, population:40389,  superficie_km2:2.153,  densite_hab_km2:18759, crimes_pour_mille:133.8, variation_pct:-2.4, repartition_pieces:{T1:25.8,T2:27.5,T3:20.1,T4:12.9,"T5+":13.6} },
  { num:7,  nom:"7ème arrondissement", surnom:"Palais-Bourbon – Tour Eiffel",       prix_medians:{2021:14995,2022:15303,2023:15000,2024:14414,2025:14413}, logements_sociaux_pct:4.1,  nb_logements_sociaux:805,   revenu_median_uc:45380, population:48015,  superficie_km2:4.09,   densite_hab_km2:11740, crimes_pour_mille:108.3, variation_pct:-2.9, repartition_pieces:{T1:20.4,T2:25.3,T3:20.0,T4:14.3,"T5+":20.0} },
  { num:8,  nom:"8ème arrondissement", surnom:"Élysée – Champs-Élysées",            prix_medians:{2021:13043,2022:13043,2023:12942,2024:12374,2025:12346}, logements_sociaux_pct:4.8,  nb_logements_sociaux:926,   revenu_median_uc:44100, population:35317,  superficie_km2:3.88,   densite_hab_km2:9102,  crimes_pour_mille:318.7, variation_pct:-0.2, repartition_pieces:{T1:22.4,T2:23.2,T3:19.1,T4:14.4,"T5+":20.9} },
  { num:9,  nom:"9ème arrondissement", surnom:"Opéra – Pigalle",                    prix_medians:{2021:11886,2022:11891,2023:11458,2024:10686,2025:11042}, logements_sociaux_pct:7.9,  nb_logements_sociaux:2097,  revenu_median_uc:37220, population:57271,  superficie_km2:2.178,  densite_hab_km2:26295, crimes_pour_mille:182.3, variation_pct:3.3,  repartition_pieces:{T1:26.2,T2:28.1,T3:23.1,T4:12.6,"T5+":9.9} },
  { num:10, nom:"10ème arrondissement",surnom:"Entrepôt – Gare du Nord",            prix_medians:{2021:10868,2022:10667,2023:10042,2024:9333, 2025:9490},  logements_sociaux_pct:14.8, nb_logements_sociaux:4859,  revenu_median_uc:29470, population:83873,  superficie_km2:2.892,  densite_hab_km2:29002, crimes_pour_mille:214.1, variation_pct:1.7,  repartition_pieces:{T1:27.8,T2:36.1,T3:21.8,T4:9.8,"T5+":4.5} },
  { num:11, nom:"11ème arrondissement",surnom:"Popincourt – Bastille",              prix_medians:{2021:11176,2022:11026,2023:10419,2024:9970, 2025:10089}, logements_sociaux_pct:15.6, nb_logements_sociaux:6665,  revenu_median_uc:30210, population:138170, superficie_km2:3.665,  densite_hab_km2:37700, crimes_pour_mille:92.8,  variation_pct:1.2,  repartition_pieces:{T1:28.8,T2:39.9,T3:21.1,T4:7.2,"T5+":2.9} },
  { num:12, nom:"12ème arrondissement",surnom:"Reuilly – Bois de Vincennes",        prix_medians:{2021:10392,2022:10200,2023:9583, 2024:8975, 2025:9091},  logements_sociaux_pct:17.9, nb_logements_sociaux:11816, revenu_median_uc:29940, population:138024, superficie_km2:16.315, densite_hab_km2:8460,  crimes_pour_mille:127.4, variation_pct:1.3,  repartition_pieces:{T1:24.2,T2:37.6,T3:24.2,T4:10.3,"T5+":3.7} },
  { num:13, nom:"13ème arrondissement",surnom:"Gobelins – Chinatown",               prix_medians:{2021:10000,2022:9897, 2023:9146, 2024:8778, 2025:8782},  logements_sociaux_pct:26.7, nb_logements_sociaux:15700, revenu_median_uc:25670, population:181271, superficie_km2:7.149,  densite_hab_km2:25356, crimes_pour_mille:84.1,  variation_pct:-4.6, repartition_pieces:{T1:29.2,T2:35.9,T3:23.8,T4:8.3,"T5+":2.9} },
  { num:14, nom:"14ème arrondissement",surnom:"Observatoire – Montparnasse",        prix_medians:{2021:10864,2022:10645,2023:10110,2024:9417, 2025:9615},  logements_sociaux_pct:19.2, nb_logements_sociaux:9005,  revenu_median_uc:29460, population:136455, superficie_km2:5.615,  densite_hab_km2:24302, crimes_pour_mille:81.3,  variation_pct:2.1,  repartition_pieces:{T1:26.4,T2:36.6,T3:23.9,T4:9.4,"T5+":3.7} },
  { num:15, nom:"15ème arrondissement",surnom:"Vaugirard – Convention",             prix_medians:{2021:10833,2022:10652,2023:10069,2024:9571, 2025:9583},  logements_sociaux_pct:15.8, nb_logements_sociaux:12855, revenu_median_uc:32780, population:229713, superficie_km2:8.495,  densite_hab_km2:27041, crimes_pour_mille:76.1,  variation_pct:0.1,  repartition_pieces:{T1:25.9,T2:33.9,T3:23.7,T4:11.5,"T5+":5.0} },
  { num:16, nom:"16ème arrondissement",surnom:"Passy – Auteuil – Bois de Boulogne",prix_medians:{2021:11838,2022:12013,2023:11550,2024:11009,2025:11111}, logements_sociaux_pct:6.7,  nb_logements_sociaux:4834,  revenu_median_uc:41550, population:159386, superficie_km2:16.373, densite_hab_km2:9735,  crimes_pour_mille:86.0,  variation_pct:0.9,  repartition_pieces:{T1:20.0,T2:22.9,T3:21.8,T4:16.9,"T5+":18.4} },
  { num:17, nom:"17ème arrondissement",surnom:"Batignolles – Ternes",               prix_medians:{2021:11470,2022:11429,2023:10875,2024:10201,2025:10323}, logements_sociaux_pct:14.3, nb_logements_sociaux:9913,  revenu_median_uc:33390, population:159212, superficie_km2:5.669,  densite_hab_km2:28085, crimes_pour_mille:80.8,  variation_pct:1.2,  repartition_pieces:{T1:22.9,T2:33.4,T3:23.1,T4:11.4,"T5+":9.1} },
  { num:18, nom:"18ème arrondissement",surnom:"Butte-Montmartre – Clignancourt",    prix_medians:{2021:10417,2022:10139,2023:9519, 2024:8810, 2025:9024},  logements_sociaux_pct:23.8, nb_logements_sociaux:12401, revenu_median_uc:24910, population:183127, superficie_km2:5.996,  densite_hab_km2:30542, crimes_pour_mille:129.0, variation_pct:2.4,  repartition_pieces:{T1:26.2,T2:43.4,T3:22.4,T4:6.2,"T5+":1.8} },
  { num:19, nom:"19ème arrondissement",surnom:"Buttes-Chaumont – La Villette",      prix_medians:{2021:9443, 2022:9222, 2023:8773, 2024:7915, 2025:8202},  logements_sociaux_pct:34.5, nb_logements_sociaux:12170, revenu_median_uc:22870, population:178691, superficie_km2:6.793,  densite_hab_km2:26305, crimes_pour_mille:105.8, variation_pct:3.6,  repartition_pieces:{T1:27.0,T2:38.5,T3:23.4,T4:8.6,"T5+":2.5} },
  { num:20, nom:"20ème arrondissement",surnom:"Ménilmontant – Belleville",          prix_medians:{2021:9692, 2022:9423, 2023:8837, 2024:8321, 2025:8409},  logements_sociaux_pct:27.9, nb_logements_sociaux:14836, revenu_median_uc:23570, population:185140, superficie_km2:5.983,  densite_hab_km2:30944, crimes_pour_mille:64.7,  variation_pct:1.1,  repartition_pieces:{T1:28.3,T2:38.5,T3:22.9,T4:8.2,"T5+":2.2} },
];

// ── État global ─────────────────────────────────────────────────────────────
let state = {
  annee: 2024,
  indicateur: "prix_m2",
  selectedArr: null,
  compareMode: false,
  compareArr: [],
};

let map, geoLayer, chartTimeline, chartPieces, chartCompareTimeline, chartCompareRadar;
let playInterval = null;

// ── GeoJSON Paris arrondissements (simplifié — fallback embarqué) ────────────
// Source : https://opendata.paris.fr/explore/dataset/arrondissements/
// Simplifié pour performance. Chargement API préféré.
const PARIS_GEOJSON_URL = "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/arrondissements/exports/geojson";

// ── Init ────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  initMap();
  initControls();
  await loadGoldData();
  updateKPIs();
  updateRanking();
});

async function loadGoldData() {
  const badge = document.getElementById("data-source-badge");
  try {
    const r = await fetch(`${API_BASE}/arrondissements`, { signal: AbortSignal.timeout(4000) });
    if (r.ok) {
      const json = await r.json();
      const arrs = json.arrondissements;
      if (arrs && arrs.length === 20) {
        GOLD_DATA = arrs.map(a => ({
          ...a,
          prix_medians: Object.fromEntries(
            Object.entries(a.prix_medians || {}).map(([y, v]) => [+y, v])
          ),
        }));
        if (badge) { badge.textContent = "● API"; badge.classList.add("badge-api"); }
        return;
      }
    }
  } catch (_) {}
  // Fallback : données Gold statiques embarquées (voir commentaire bloc GOLD_DATA)
  if (badge) { badge.textContent = "● Hors ligne"; badge.classList.add("badge-offline"); }
}

// ── Carte Leaflet ────────────────────────────────────────────────────────────
function initMap() {
  map = L.map("map", { zoomControl: true, attributionControl: true }).setView([48.8566, 2.3522], 12);

  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: "abcd",
    maxZoom: 19,
  }).addTo(map);

  loadGeoJSON();
}

async function loadGeoJSON() {
  // Essaie l'API locale, puis OpenData Paris, puis fallback numérique
  let geojson = null;

  try {
    const r = await fetch(`${API_BASE}/geojson`, { signal: AbortSignal.timeout(3000) });
    if (r.ok) geojson = await r.json();
  } catch (_) {}

  if (!geojson) {
    try {
      const r = await fetch(PARIS_GEOJSON_URL, { signal: AbortSignal.timeout(8000) });
      if (r.ok) geojson = await r.json();
    } catch (_) {}
  }

  if (geojson) {
    renderGeoLayer(geojson);
  } else {
    document.getElementById("map-info").textContent =
      "GeoJSON indisponible — démarrez l'API ou vérifiez la connexion.";
  }
}

function getIndicatorValue(d, annee) {
  switch (state.indicateur) {
    case "prix_m2":               return d.prix_medians?.[annee] ?? null;
    case "logements_sociaux_pct": return d.logements_sociaux_pct ?? null;
    case "revenu_median_uc":      return d.revenu_median_uc ?? null;
    case "crimes_pour_mille":     return d.crimes_pour_mille ?? null;
    case "densite_hab_km2":       return d.densite_hab_km2 ?? null;
    case "variation_pct":         return d.variation_pct ?? null;
  }
}

function getColorScale(indicator) {
  // Returns [stops] from low to high : [color, label]
  const scales = {
    prix_m2:               { colors: ["#e8effe","#bdd0fb","#6b94f5","#2451c8","#0d1b4b"], labels: ["< 9k","9–11k","11–13k","13–15k","> 15k €/m²"] },
    logements_sociaux_pct: { colors: ["#f0fdf4","#bbf7d0","#4ade80","#16a34a","#14532d"], labels: ["< 5%","5–12%","12–20%","20–28%","> 28%"] },
    revenu_median_uc:      { colors: ["#fff7ed","#fed7aa","#fb923c","#ea580c","#7c2d12"], labels: ["< 22k","22–28k","28–34k","34–40k","> 40k €"] },
    crimes_pour_mille:     { colors: ["#f0fdf4","#fef9c3","#fde047","#ef4444","#7f1d1d"], labels: ["< 80","80–130","130–200","200–350","> 350"] },
    densite_hab_km2:       { colors: ["#f8fafc","#cbd5e1","#64748b","#334155","#0f172a"], labels: ["< 10k","10–20k","20–30k","30–35k","> 35k"] },
    variation_pct:         { colors: ["#7f1d1d","#fca5a5","#e5e7eb","#86efac","#14532d"], labels: ["< -3%","-3 à -1%","-1 à +1%","+1 à +3%","> +3%"] },
  };
  return scales[indicator] || scales.prix_m2;
}

function getColor(value, indicator) {
  const thresholds = {
    prix_m2:               [9000,  11000, 13000, 15000],
    logements_sociaux_pct: [5,     12,    20,    28],
    revenu_median_uc:      [22000, 28000, 34000, 40000],
    crimes_pour_mille:     [80,    130,   200,   350],
    densite_hab_km2:       [10000, 20000, 30000, 35000],
    variation_pct:         [-3,    -1,    1,     3],
  };
  const scale = getColorScale(indicator);
  const thresh = thresholds[indicator] || thresholds.prix_m2;
  if (value === null || value === undefined) return "#e5e7eb";
  if (value < thresh[0]) return scale.colors[0];
  if (value < thresh[1]) return scale.colors[1];
  if (value < thresh[2]) return scale.colors[2];
  if (value < thresh[3]) return scale.colors[3];
  return scale.colors[4];
}

function renderGeoLayer(geojson) {
  if (geoLayer) map.removeLayer(geoLayer);

  geoLayer = L.geoJSON(geojson, {
    style: feature => styleFeature(feature),
    onEachFeature: (feature, layer) => {
      layer.on({
        mouseover: e => onHover(e, feature),
        mouseout:  e => onOut(e),
        click:     e => onClickArr(e, feature),
      });
    },
  }).addTo(map);

  addArrLabels();
  updateLegend();
}

let arrLabelLayer = null;
function addArrLabels() {
  if (arrLabelLayer) arrLabelLayer.clearLayers();
  else arrLabelLayer = L.layerGroup().addTo(map);

  Object.entries(ARR_CENTROIDS).forEach(([num, latlng]) => {
    L.marker(latlng, {
      icon: L.divIcon({
        className: "arr-label-wrapper",
        html: `<div class="arr-pill">${num}</div>`,
        iconSize: null,
        iconAnchor: [14, 11],
      }),
      interactive: false,
      keyboard: false,
    }).addTo(arrLabelLayer);
  });
}

function styleFeature(feature) {
  const props = feature.properties || {};
  const arrNum = props.arrondissement || props.c_ar;
  const d = GOLD_DATA.find(a => a.num === +arrNum);
  const val = d ? getIndicatorValue(d, state.annee) : null;

  return {
    fillColor: getColor(val, state.indicateur),
    fillOpacity: 0.80,
    color: "#334155",
    weight: 2,
  };
}

function onHover(e, feature) {
  const layer = e.target;
  layer.setStyle({ weight: 3, color: "#0d1b4b", fillOpacity: 0.92 });

  const props = feature.properties || {};
  const arrNum = +(props.arrondissement || props.c_ar);
  const d = GOLD_DATA.find(a => a.num === arrNum);
  if (!d) return;

  const prix = d.prix_medians?.[state.annee];
  const variation = d.variation_pct;
  const varStr = variation != null
    ? `${variation > 0 ? "+" : ""}${variation.toFixed(1)}%`
    : "—";

  const infoEl = document.getElementById("map-info");
  infoEl.innerHTML = `
    <strong>${d.num}${ordinal(d.num)} — ${d.surnom}</strong> &nbsp;|&nbsp;
    Prix/m² ${state.annee} : <strong>${prix ? prix.toLocaleString("fr-FR") + " €" : "—"}</strong> &nbsp;|&nbsp;
    Var. annuelle : <strong class="${variation < 0 ? "neg" : "pos"}">${varStr}</strong> &nbsp;|&nbsp;
    Logt. soc. : <strong>${d.logements_sociaux_pct}%</strong>
  `;
}

function onOut(e) {
  if (geoLayer) geoLayer.resetStyle(e.target);
  document.getElementById("map-info").innerHTML = "Survolez un arrondissement pour voir ses indicateurs";
}

function onClickArr(_e, feature) {
  const props = feature.properties || {};
  const arrNum = +(props.arrondissement || props.c_ar);
  const d = GOLD_DATA.find(a => a.num === arrNum);
  if (!d) return;

  if (state.compareMode) {
    if (!state.compareArr.includes(arrNum)) {
      state.compareArr.push(arrNum);
    }
    if (state.compareArr.length === 2) {
      showComparison(state.compareArr[0], state.compareArr[1]);
      state.compareArr = [];
    } else {
      document.getElementById("compare-hint").textContent =
        `${ordinal(arrNum)} sélectionné — cliquez un 2ème arrondissement`;
    }
    return;
  }

  state.selectedArr = arrNum;
  showDetailPanel(d);
}

// ── Légende ─────────────────────────────────────────────────────────────────
function updateLegend() {
  const scale = getColorScale(state.indicateur);
  const legendEl = document.getElementById("map-legend");
  const titles = {
    prix_m2:               "Prix médian €/m²",
    logements_sociaux_pct: "Logements sociaux",
    revenu_median_uc:      "Revenu médian/UC",
    crimes_pour_mille:     "Criminalité/1 000 hab",
    densite_hab_km2:       "Densité hab/km²",
    variation_pct:         "Variation 2024→2025",
  };
  legendEl.innerHTML = `
    <div class="legend-title">${titles[state.indicateur]}</div>
    <div class="legend-scale">
      ${scale.colors.map((c, i) => `
        <div class="legend-item">
          <div class="legend-swatch" style="background:${c}"></div>
          <span>${scale.labels[i]}</span>
        </div>
      `).join("")}
    </div>
  `;
}

// ── Panneau détail ───────────────────────────────────────────────────────────
function showDetailPanel(d) {
  document.getElementById("panel-global").classList.add("hidden");
  document.getElementById("panel-detail").classList.remove("hidden");

  document.getElementById("detail-title").textContent = `${d.num}${ordinal(d.num)} — ${d.surnom}`;

  const prix = d.prix_medians?.[state.annee];
  const variation = d.variation_pct;

  document.getElementById("d-prix").textContent =
    prix ? `${prix.toLocaleString("fr-FR")} €/m²` : "—";
  document.getElementById("d-variation").innerHTML =
    variation != null
      ? `<span class="${variation < 0 ? "neg" : "pos"}">${variation > 0 ? "+" : ""}${variation.toFixed(1)}%</span>`
      : "—";
  document.getElementById("d-logsoc").textContent  = `${d.logements_sociaux_pct}%`;
  document.getElementById("d-revenu").textContent  = d.revenu_median_uc ? `${d.revenu_median_uc.toLocaleString("fr-FR")} €` : "—";
  document.getElementById("d-pop").textContent     = d.population ? d.population.toLocaleString("fr-FR") : "—";
  document.getElementById("d-densite").textContent = d.densite_hab_km2 ? `${d.densite_hab_km2.toLocaleString("fr-FR")}/km²` : "—";
  document.getElementById("d-crime").textContent   = d.crimes_pour_mille ?? "—";

  renderChartTimeline(d);
  renderChartPieces(d);
}

function renderChartTimeline(d) {
  const ctx = document.getElementById("chart-timeline").getContext("2d");
  if (chartTimeline) chartTimeline.destroy();

  const labels = ANNEES;
  const values = ANNEES.map(y => d.prix_medians?.[y] ?? null);

  chartTimeline = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Prix médian €/m²",
        data: values,
        borderColor: "#2451c8",
        backgroundColor: "rgba(36,81,200,0.10)",
        borderWidth: 2.5,
        pointBackgroundColor: "#2451c8",
        pointRadius: 4,
        tension: 0.35,
        fill: true,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        title: { display: true, text: `Évolution prix/m² — ${d.nom}`, font: { size: 11, weight: "600" }, color: "#1a1f36" },
        tooltip: { callbacks: { label: ctx => `${ctx.parsed.y.toLocaleString("fr-FR")} €/m²` } },
      },
      scales: {
        y: { ticks: { callback: v => `${(v/1000).toFixed(0)}k €`, font: { size: 10 } }, grid: { color: "#e2e8f4" } },
        x: { ticks: { font: { size: 10 } } },
      },
    },
  });
}

function renderChartPieces(d) {
  const ctx = document.getElementById("chart-pieces").getContext("2d");
  if (chartPieces) chartPieces.destroy();

  const pieces = d.repartition_pieces || {};
  const labels = ["T1", "T2", "T3", "T4", "T5+"];
  const values = labels.map(l => pieces[l] ?? 0);
  const colors = ["#6b94f5","#2451c8","#1a2f7a","#0d1b4b","#bdd0fb"];

  chartPieces = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: colors, borderWidth: 2, borderColor: "#fff" }],
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: {
        legend: { position: "right", labels: { font: { size: 10 }, boxWidth: 12 } },
        title: { display: true, text: "Répartition typologies logements", font: { size: 11, weight: "600" }, color: "#1a1f36" },
        tooltip: { callbacks: { label: ctx => `${ctx.label} : ${ctx.parsed.toFixed(1)}%` } },
      },
    },
  });
}

// ── KPIs ─────────────────────────────────────────────────────────────────────
function updateKPIs() {
  const annee = state.annee;
  document.getElementById("panel-year").textContent = annee;
  document.getElementById("ranking-year").textContent = annee;

  const prices = GOLD_DATA.map(d => ({ num: d.num, nom: d.nom, prix: d.prix_medians?.[annee] }))
    .filter(d => d.prix != null)
    .sort((a, b) => b.prix - a.prix);

  if (!prices.length) return;

  const avg = Math.round(prices.reduce((s, d) => s + d.prix, 0) / prices.length);
  document.getElementById("kpi-prix-moyen").textContent = `${avg.toLocaleString("fr-FR")} €/m²`;
  document.getElementById("kpi-arr-max").textContent = `${prices[0].num}${ordinal(prices[0].num)} — ${prices[0].prix.toLocaleString("fr-FR")} €`;
  document.getElementById("kpi-arr-min").textContent = `${prices[prices.length-1].num}${ordinal(prices[prices.length-1].num)} — ${prices[prices.length-1].prix.toLocaleString("fr-FR")} €`;

  const avgVar = GOLD_DATA.reduce((s, d) => s + (d.variation_pct ?? 0), 0) / GOLD_DATA.length;
  const varEl = document.getElementById("kpi-variation");
  varEl.textContent = `${avgVar > 0 ? "+" : ""}${avgVar.toFixed(1)}%`;
  varEl.className = `kpi-value ${avgVar < 0 ? "neg" : "pos"}`;
}

// ── Classement ──────────────────────────────────────────────────────────────
function updateRanking() {
  const annee = state.annee;
  const sorted = [...GOLD_DATA]
    .filter(d => d.prix_medians?.[annee] != null)
    .sort((a, b) => b.prix_medians[annee] - a.prix_medians[annee]);

  const maxPrix = sorted[0]?.prix_medians[annee] || 1;
  const rankEl = document.getElementById("ranking-list");

  rankEl.innerHTML = sorted.map((d, i) => {
    const prix = d.prix_medians[annee];
    const pct = (prix / maxPrix) * 100;
    return `
      <div class="rank-item" data-arr="${d.num}">
        <div class="rank-num ${i < 3 ? "top3" : ""}">${i + 1}</div>
        <div class="rank-name">${d.num}${ordinal(d.num)}</div>
        <div class="rank-bar-wrapper"><div class="rank-bar" style="width:${pct}%"></div></div>
        <div class="rank-price">${prix.toLocaleString("fr-FR")} €</div>
      </div>
    `;
  }).join("");

  rankEl.querySelectorAll(".rank-item").forEach(el => {
    el.addEventListener("click", () => {
      const arrNum = +el.dataset.arr;
      const d = GOLD_DATA.find(a => a.num === arrNum);
      if (d) showDetailPanel(d);
    });
  });
}

// ── Comparaison ─────────────────────────────────────────────────────────────
function showComparison(num1, num2) {
  const d1 = GOLD_DATA.find(a => a.num === num1);
  const d2 = GOLD_DATA.find(a => a.num === num2);
  if (!d1 || !d2) return;

  document.getElementById("compare-overlay").classList.remove("hidden");

  // Dernière année disponible dans les données
  const latestYear = Math.max(...ANNEES.filter(y =>
    d1.prix_medians?.[y] != null || d2.prix_medians?.[y] != null
  ));

  const indicators = [
    { key: "prix_m2_latest",       label: `Prix/m² ${latestYear}`, fmt: v => `${v?.toLocaleString("fr-FR")} €`, higher: "worse" },
    { key: "variation_pct",   label: "Variation annuelle",    fmt: v => v != null ? `${v > 0 ? "+" : ""}${v.toFixed(1)}%` : "—", higher: "better" },
    { key: "logements_sociaux_pct",label: "Logements sociaux",     fmt: v => `${v}%`, higher: "better" },
    { key: "revenu_median_uc",     label: "Revenu médian/UC",      fmt: v => `${v?.toLocaleString("fr-FR")} €`, higher: "better" },
    { key: "crimes_pour_mille",    label: "Criminalité/1000",      fmt: v => v, higher: "worse" },
    { key: "densite_hab_km2",      label: "Densité/km²",           fmt: v => v?.toLocaleString("fr-FR"), higher: null },
    { key: "population",           label: "Population",            fmt: v => v?.toLocaleString("fr-FR"), higher: null },
  ];

  const getVal = (d, key) => {
    if (key === "prix_m2_latest") return d.prix_medians?.[latestYear];
    return d[key];
  };

  const renderCol = (d, colId) => {
    const colEl = document.getElementById(colId);
    colEl.innerHTML = `
      <h4>${d.num}${ordinal(d.num)} — ${d.surnom}</h4>
      ${indicators.map(ind => {
        const v1 = getVal(d1, ind.key);
        const v2 = getVal(d2, ind.key);
        const v  = getVal(d, ind.key);
        let cls = "";
        if (ind.higher && v1 != null && v2 != null) {
          const better = ind.higher === "better"
            ? (d.num === d1.num ? v1 > v2 : v2 > v1)
            : (d.num === d1.num ? v1 < v2 : v2 < v1);
          cls = better ? "better" : (v1 === v2 ? "" : "worse");
        }
        return `
          <div class="compare-stat">
            <div class="cs-label">${ind.label}</div>
            <div class="cs-val ${cls}">${ind.fmt(v)}</div>
          </div>
        `;
      }).join("")}
    `;
  };

  renderCol(d1, "compare-col-1");
  renderCol(d2, "compare-col-2");

  // Timeline comparaison
  const ctxT = document.getElementById("chart-compare-timeline").getContext("2d");
  if (chartCompareTimeline) chartCompareTimeline.destroy();
  chartCompareTimeline = new Chart(ctxT, {
    type: "line",
    data: {
      labels: ANNEES,
      datasets: [
        {
          label: `${d1.num}${ordinal(d1.num)}`,
          data: ANNEES.map(y => d1.prix_medians?.[y] ?? null),
          borderColor: "#2451c8", backgroundColor: "rgba(36,81,200,0.08)",
          borderWidth: 2.5, tension: 0.35, fill: true, pointRadius: 4,
        },
        {
          label: `${d2.num}${ordinal(d2.num)}`,
          data: ANNEES.map(y => d2.prix_medians?.[y] ?? null),
          borderColor: "#16a34a", backgroundColor: "rgba(22,163,74,0.08)",
          borderWidth: 2.5, tension: 0.35, fill: true, pointRadius: 4,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      plugins: {
        title: { display: true, text: "Évolution prix/m² comparée", font: { size: 12, weight: "700" } },
        tooltip: { callbacks: { label: ctx => `${ctx.dataset.label} : ${ctx.parsed.y.toLocaleString("fr-FR")} €/m²` } },
      },
      scales: {
        y: { ticks: { callback: v => `${(v/1000).toFixed(0)}k €` } },
      },
    },
  });

  // Radar
  const ctxR = document.getElementById("chart-compare-radar").getContext("2d");
  if (chartCompareRadar) chartCompareRadar.destroy();

  const normalize = (val, min, max) => max === min ? 50 : ((val - min) / (max - min)) * 100;
  const radarIndicators = [
    { key: "prix_m2_latest", label: "Prix/m²", min: 8000, max: 15000, inv: true },
    { key: "logements_sociaux_pct", label: "Logt. sociaux", min: 3, max: 35 },
    { key: "revenu_median_uc", label: "Revenus", min: 19000, max: 47000 },
    { key: "densite_hab_km2", label: "Densité", min: 8000, max: 40000 },
    { key: "crimes_pour_mille", label: "Criminalité", min: 45, max: 200, inv: true },
  ];

  const makeRadar = d => radarIndicators.map(ind => {
    const v = getVal(d, ind.key);
    const n = normalize(v ?? ind.min, ind.min, ind.max);
    return ind.inv ? 100 - n : n;
  });

  chartCompareRadar = new Chart(ctxR, {
    type: "radar",
    data: {
      labels: radarIndicators.map(i => i.label),
      datasets: [
        { label: `${d1.num}${ordinal(d1.num)}`, data: makeRadar(d1), borderColor: "#2451c8", backgroundColor: "rgba(36,81,200,0.2)", pointBackgroundColor: "#2451c8" },
        { label: `${d2.num}${ordinal(d2.num)}`, data: makeRadar(d2), borderColor: "#16a34a", backgroundColor: "rgba(22,163,74,0.2)", pointBackgroundColor: "#16a34a" },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: true,
      scales: { r: { min: 0, max: 100, ticks: { display: false }, grid: { color: "#e2e8f4" } } },
      plugins: {
        title: { display: true, text: "Profil comparatif (score normalisé)", font: { size: 12, weight: "700" } },
      },
    },
  });
}

// ── Contrôles ────────────────────────────────────────────────────────────────
function initControls() {
  // Indicateur — désactive le slider et affiche l'année source pour les indicateurs sans historique
  document.getElementById("indicator-select").addEventListener("change", e => {
    state.indicateur = e.target.value;
    const isPrix = state.indicateur === "prix_m2";
    const yearNote   = document.getElementById("year-note");
    const yearSlider = document.getElementById("year-slider");
    if (isPrix) {
      yearNote.classList.add("hidden");
    } else {
      const dateLabel = INDICATOR_DATES[state.indicateur] || "Donnée statique";
      yearNote.textContent = `— ${dateLabel}`;
      yearNote.classList.remove("hidden");
    }
    yearSlider.disabled = !isPrix;
    yearSlider.style.opacity = isPrix ? "1" : "0.35";
    if (!isPrix) stopAnimation();
    if (geoLayer) geoLayer.setStyle(f => styleFeature(f));
    updateLegend();
  });

  // Année
  const yearSlider = document.getElementById("year-slider");
  yearSlider.addEventListener("input", () => {
    stopAnimation();
    applyYear(+yearSlider.value);
  });

  // Bouton Play — anime l'évolution annuelle
  const playBtn = document.getElementById("play-btn");
  playBtn.addEventListener("click", () => {
    if (playInterval) {
      stopAnimation();
    } else {
      startAnimation();
    }
  });

  // Mode comparaison
  const compareBtn = document.getElementById("compare-btn");
  compareBtn.addEventListener("click", () => {
    state.compareMode = !state.compareMode;
    state.compareArr = [];
    compareBtn.textContent = state.compareMode ? "Désactiver" : "Activer";
    compareBtn.classList.toggle("active", state.compareMode);
    document.getElementById("compare-hint").classList.toggle("hidden", !state.compareMode);
    if (state.compareMode) {
      document.getElementById("compare-hint").textContent = "Cliquez 2 arrondissements";
    }
  });

  // Fermer comparaison
  document.getElementById("compare-close").addEventListener("click", () => {
    document.getElementById("compare-overlay").classList.add("hidden");
    state.compareMode = false;
    document.getElementById("compare-btn").textContent = "Activer";
    document.getElementById("compare-btn").classList.remove("active");
    document.getElementById("compare-hint").classList.add("hidden");
  });

  // Onglets
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.add("hidden"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.remove("hidden");
    });
  });
}

// ── Animation timeline ────────────────────────────────────────────────────────
function applyYear(annee) {
  state.annee = annee;
  const yearSlider = document.getElementById("year-slider");
  yearSlider.value = annee;
  document.getElementById("current-year-badge").textContent = annee;
  document.getElementById("panel-year").textContent = annee;
  document.getElementById("ranking-year").textContent = annee;
  if (geoLayer) geoLayer.setStyle(f => styleFeature(f));
  updateKPIs();
  updateRanking();
  if (state.selectedArr) {
    const d = GOLD_DATA.find(a => a.num === state.selectedArr);
    if (d) document.getElementById("d-prix").textContent =
      `${(d.prix_medians?.[annee] ?? "—").toLocaleString("fr-FR")} €/m²`;
  }
}

function startAnimation() {
  const playBtn = document.getElementById("play-btn");
  playBtn.textContent = "⏸";
  playBtn.classList.add("playing");
  playBtn.title = "Pause";

  const annees = ANNEES;
  let idx = annees.indexOf(state.annee);
  if (idx === annees.length - 1) idx = -1;

  playInterval = setInterval(() => {
    idx = (idx + 1) % annees.length;
    applyYear(annees[idx]);
    if (idx === annees.length - 1) {
      stopAnimation();
    }
  }, 1200);
}

function stopAnimation() {
  if (playInterval) {
    clearInterval(playInterval);
    playInterval = null;
  }
  const playBtn = document.getElementById("play-btn");
  if (playBtn) {
    playBtn.textContent = "▶";
    playBtn.classList.remove("playing");
    playBtn.title = "Animer l'évolution temporelle";
  }
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function ordinal(n) {
  return n === 1 ? "er" : "ème";
}
