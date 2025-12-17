
/**
 * Footprint Chart Application
 * Optimized for performance and usability.
 */

// Global State
const state = {
    symbol: null,
    symbols: [],
    bars: [], // Array of {ts, levels: {price: {bid, ask}}}
    dom: { bids: {}, asks: {} },
    view: {
        offsetX: 0, // Time offset (pixels)
        offsetY: 0, // Price offset (pixels)
        scaleX: 120, // INCREASED ZOOM (Wider bars)
        scaleY: 20, // Pixel per price tick (or relative)
        barWidth: 50,
        priceStep: 0.05, // Will be auto-detected
    },
    isDragging: false,
    lastMouse: { x: 0, y: 0 },
    canvasSize: { w: 0, h: 0 }
};

// DOM Elements
const elements = {
    fpCanvas: document.getElementById('fpCanvas'),
    domCanvas: document.getElementById('domCanvas'),
    symbolSearch: document.getElementById('symbolSearch'),
    searchResults: document.getElementById('searchResults'),
    msgOverlay: document.getElementById('msgOverlay'),
};

const ctx = elements.fpCanvas.getContext('2d', { alpha: false }); // Optimize for no transparency on bg
const domCtx = elements.domCanvas.getContext('2d');

// --- Initialization ---

// --- Loop ---
function loop() {
    draw();
    requestAnimationFrame(loop);
}

// --- Initialization ---

async function init() {
    resize();
    window.addEventListener('resize', resize);

    // Input Handling
    initInputAPI();

    // chart interactions
    elements.fpCanvas.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mouseup', onMouseUp);
    window.addEventListener('mousemove', onMouseMove);
    elements.fpCanvas.addEventListener('wheel', onWheel);

    // Initial Fetch
    await fetchSymbols();

    // Check URL Params for deep linking (e.g. from /trades)
    const urlParams = new URLSearchParams(window.location.search);
    const linkedSymbol = urlParams.get('symbol');
    if (linkedSymbol) {
        // Decode in case of special chars
        const sym = decodeURIComponent(linkedSymbol);
        console.log("Deep Link loading:", sym);
        elements.symbolSearch.value = sym;
        loadHistory(sym);
    }

    connectWS();

    // Start Loop
    loop();
}

function resize() {
    const container = document.getElementById('chart-container');
    if (container) {
        elements.fpCanvas.width = container.clientWidth;
        elements.fpCanvas.height = container.clientHeight;
        state.canvasSize.w = elements.fpCanvas.width;
        state.canvasSize.h = elements.fpCanvas.height;
    }
}

// --- Data Layer ---

async function fetchSymbols() {
    try {
        const res = await fetch('/symbols');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (Array.isArray(data)) {
            state.symbols = data;
        } else {
            console.error("Symbols data is not an array:", data);
            state.symbols = [];
        }
        populateSearch(state.symbols);
    } catch (e) {
        console.error("Failed to fetch symbols", e);
        state.symbols = []; // Fallback
        populateSearch(state.symbols);
    }
}

async function loadHistory(symbol) {
    setOverlay(`Loading ${symbol}...`);
    state.bars = [];
    state.symbol = symbol;

    // Reset State cleanly for new symbol
    // Reset State cleanly for new symbol
    state.dom = { bids: {}, asks: {} };
    state.view.offsetY = 0; // RESET Y to allow Auto-Center to find new price range


    try {
        const res = await fetch(`/history/${encodeURIComponent(symbol)}`);
        const data = await res.json();

        // Process data
        const validBars = [];

        if (Array.isArray(data)) {
            data.forEach(bar => {
                // Filter invalid data (e.g. raw quotes or signals mixed in DB)
                if (!bar.levels || Object.keys(bar.levels).length === 0) return;

                const levels = {};
                let totalVol = 0;
                let maxVol = 0;
                let hasValidLevels = false;

                Object.entries(bar.levels).forEach(([pStr, val]) => {
                    const p = parseFloat(pStr);
                    if (isNaN(p)) return;

                    levels[p] = val;
                    const vol = (val.bid || 0) + (val.ask || 0);
                    totalVol += vol;
                    if (vol > maxVol) maxVol = vol;
                    hasValidLevels = true;
                });

                if (hasValidLevels) {
                    validBars.push({
                        ts: bar.ts || bar.ltt || 0,
                        levels: levels,
                        totalVol,
                        maxVol
                    });
                }
            });
        }

        state.bars = validBars;
        state.bars.sort((a, b) => a.ts - b.ts);

        // Calc Volume Stats for Bubbles
        calculateVolumeStats();

        // LOAD TRADES for this symbol
        try {
            const tRes = await fetch(`/api/trades/${encodeURIComponent(symbol)}`);
            if (tRes.ok) {
                state.trades = await tRes.json();
            } else {
                state.trades = [];
            }
        } catch (e) {
            console.error("Failed to load trades", e);
            state.trades = [];
        }

        // Attempt Auto-Center immediately after load
        checkAutoCenter();

        // Always reset end index on load to valid range
        if (state.bars.length > 0) {
            state.view.endIndex = state.bars.length + 2;
        }

        setOverlay(null);
    } catch (e) {
        console.error(e);
        setOverlay("Error loading history");
    }
}

function connectWS() {
    const ws = new WebSocket(`ws://${location.host}/ws`);
    ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.type === 'footprint' && msg.symbol === state.symbol) {
            handleFootprintUpdate(msg);
        } else if (msg.type === 'dom' && msg.symbol === state.symbol) {
            state.dom = msg;
            // drawDOM(); // drawDOM is handled in loop? No, it's separate canvas.
            requestAnimationFrame(drawDOM);
            // Critical: If we have no bars yet (no history), the DOM can tell us the price!
            checkAutoCenter();
        }
    };
    ws.onclose = () => setTimeout(connectWS, 2000);
}

// ... (Other functions) ...

function populateSearch(list) {
    elements.searchResults.innerHTML = '';
    if (!Array.isArray(list)) return;

    list.slice(0, 100).forEach(sym => {
        const div = document.createElement('div');
        div.className = 'search-item';
        div.textContent = sym;
        div.onclick = () => {
            elements.symbolSearch.value = sym;
            elements.searchResults.classList.remove('visible');
            loadHistory(sym);
        };
        elements.searchResults.appendChild(div);
    });
}


// --- Auto-Centering Logic ---

function checkAutoCenter() {
    // Only center if we haven't set a valid offset yet
    if (state.view.offsetY !== 0) return;

    let targetPrice = null;

    // 1. Try to get price from Bars (History or Live)
    if (state.bars.length > 0) {
        // Scan backwards for valid levels
        for (let i = state.bars.length - 1; i >= 0; i--) {
            const levels = state.bars[i].levels;
            if (!levels) continue;

            const prices = Object.keys(levels).map(parseFloat).filter(p => !isNaN(p));
            if (prices.length > 0) {
                const minP = Math.min(...prices);
                const maxP = Math.max(...prices);
                targetPrice = (minP + maxP) / 2;
                break;
            }
        }
    }

    // 2. If no bars, try to get price from DOM (Live Quote)
    if (targetPrice === null) {
        const bids = Object.keys(state.dom.bids || {}).map(parseFloat);
        const asks = Object.keys(state.dom.asks || {}).map(parseFloat);
        const all = [...bids, ...asks].filter(p => !isNaN(p));

        if (all.length > 0) {
            targetPrice = (Math.min(...all) + Math.max(...all)) / 2;
        }
    }

    // Apply
    if (targetPrice !== null && targetPrice !== 0) {
        console.log(`[AutoCenter] Centering View on ${targetPrice}`);
        state.view.offsetY = targetPrice;

        // Also snap X axis if we have bars
        if (state.bars.length > 0) {
            state.view.endIndex = state.bars.length + 2;
        }
    }
}

function handleFootprintUpdate(msg) {
    // Check if we have this bar
    const existing = state.bars.find(b => b.ts === msg.ts);

    // Process levels
    const levels = {};
    let totalVol = 0;
    let maxVol = 0;
    Object.entries(msg.levels).forEach(([pStr, val]) => {
        const p = parseFloat(pStr);
        levels[p] = val;
        const vol = (val.bid || 0) + (val.ask || 0);
        totalVol += vol;
        if (vol > maxVol) maxVol = vol;
    });

    if (existing) {
        existing.levels = levels;
        existing.totalVol = totalVol;
        existing.maxVol = maxVol;
    } else {
        state.bars.push({
            ts: msg.ts,
            levels: levels,
            totalVol,
            maxVol
        });

        // 2. Auto-Scroll Time (Sticky Live)
        // Only if we are already near the end (user watching live)
        // or if we just started.
        const isNearEnd = state.view.endIndex >= state.bars.length - 5;

        if (isNearEnd) {
            state.view.endIndex = state.bars.length + 2;
        }
    }

    // Always check if we need to center (e.g. first bar arrived)

    calculateVolumeStats(); // Update stats on live tick
    checkAutoCenter();
}

// --- Interaction ---

function initInputAPI() {
    elements.symbolSearch.addEventListener('input', (e) => {
        const val = e.target.value.toLowerCase();
        const matches = state.symbols.filter(s => s.toLowerCase().includes(val));
        populateSearch(matches);
    });

    elements.symbolSearch.addEventListener('focus', () => {
        elements.searchResults.classList.add('visible');
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!elements.searchContainer.contains(e.target)) {
            elements.searchResults.classList.remove('visible');
        }
    });

    // Hack for getting the container for the click listener
    elements.searchContainer = document.querySelector('.search-container');
}

function populateSearch(list) {
    elements.searchResults.innerHTML = '';
    list.slice(0, 100).forEach(sym => {
        const div = document.createElement('div');
        div.className = 'search-item';
        div.textContent = sym;
        div.onclick = () => {
            elements.symbolSearch.value = sym;
            elements.searchResults.classList.remove('visible');
            loadHistory(sym);
        };
        elements.searchResults.appendChild(div);
    });
}

// Mouse Interaction
function onMouseDown(e) {
    state.isDragging = true;
    state.lastMouse = { x: e.clientX, y: e.clientY };
}

function onMouseUp() {
    state.isDragging = false;
}

function onMouseMove(e) {
    if (state.isDragging) {
        const dx = e.clientX - state.lastMouse.x;
        const dy = e.clientY - state.lastMouse.y;

        // Pan X (index based)
        // dx pixels -> how many bars?
        // 1 bar = state.view.scaleX pixels
        state.view.endIndex -= dx / state.view.scaleX;

        // Pan Y (Price)
        // dy pixels -> price
        // 1 price unit = state.view.scaleY
        state.view.offsetY += dy / state.view.scaleY;

        state.lastMouse = { x: e.clientX, y: e.clientY };
        requestAnimationFrame(draw);
    }
}


// --- Interaction ---

function onWheel(e) {
    e.preventDefault();

    // Trackpad Logic:
    // 1. Pinch Gesture (Browser sends Ctrl + Wheel) -> Zoom X (Time)
    // 2. Normal Vertical Scroll (deltaY) -> Pan X (Time) ... or Zoom X if requested? 
    //    User asked "default should be X axis zoom". 
    //    Let's make Plain Scroll = Zoom X (aggressive)
    //    And Pinch (Ctrl) = Zoom X (Fine tune)
    //    Shift + Scroll = Zoom Y (Price)

    // Sensitivity adjustment
    const isTrackpad = Math.abs(e.deltaY) < 50;
    const factor = isTrackpad ? 1.02 : 1.1;

    // Zoom Direction
    const direction = e.deltaY > 0 ? 1 / factor : factor;

    if (e.ctrlKey) {
        // PINCH GESTURE usually. 
        // User complained "Only Y Zoomed" when trying to zoom.
        // So they want Pinch -> Zoom X.
        state.view.scaleX = Math.max(1, state.view.scaleX * direction);
        state.view.scaleX = Math.min(1000, state.view.scaleX);
    } else if (e.shiftKey) {
        // Shift -> Zoom Y Area (Manual override of auto-fit)
        // We might need to disable auto-fit if user manually zooms? 
        // For now, let's let Auto-Fit take precedence in draw() loop 
        // making manual Y zoom temporary or ignored.
        // If Auto-Fit is enabling, we shouldn't manually zoom Y.
        // Let's assume Auto-Fit is always ON for now as per "Clean & Representation" request.
    } else {
        // Plain Scroll -> ZOOM X (as requested "Default X axis zoom")
        // Note: Standard apps PAN on scroll, but user specifically asked for Zoom default.
        state.view.scaleX = Math.max(1, state.view.scaleX * direction);
        state.view.scaleX = Math.min(1000, state.view.scaleX);
    }

    requestAnimationFrame(draw);
}

// Override Mouse Move to Pan X (Time) when dragging
function onMouseMove(e) {
    if (state.isDragging) {
        const dx = e.clientX - state.lastMouse.x;
        const dy = e.clientY - state.lastMouse.y;

        // Pan X (Time)
        state.view.endIndex -= dx / state.view.scaleX;

        // Pan Y (Price) - Modified
        // Since we have Auto-Fit Y, manual Y panning fights with it.
        // But dragging Y is useful to inspect. 
        // Let's allow it, but Auto-Fit might snap it back if we don't disable Auto-Fit.
        // For the "Middle 10%" fix, we need Auto-Scale.
        // Let's rely on Auto-Scale logic in draw().

        state.lastMouse = { x: e.clientX, y: e.clientY };
        requestAnimationFrame(draw);
    }
}

// --- Rendering ---

function draw() {
    const w = state.canvasSize.w;
    const h = state.canvasSize.h;

    // Background
    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, w, h);

    if (state.bars.length === 0) return;

    // 1. Calculate Visible Index Range
    const barWidth = state.view.scaleX;
    // Ensure barWidth is reasonable
    if (!barWidth || isNaN(barWidth)) state.view.scaleX = 60;

    // Safety check for huge indices
    if (Math.abs(state.view.endIndex) > 1e6) state.view.endIndex = state.bars.length + 2;

    const visibleBarsCount = Math.ceil(w / state.view.scaleX) + 1;
    let endIndex = Math.floor(state.view.endIndex);
    let startIndex = endIndex - visibleBarsCount;

    // 2. Auto-Fit Y-Axis (Price) Logic [AGGRESSIVE]
    // Scan visible bars for Min/Max High/Low
    let minP = Infinity;
    let maxP = -Infinity;
    let hasVisibleData = false;

    // Limit scan to visible range
    for (let i = startIndex; i <= endIndex; i++) {
        if (i >= 0 && i < state.bars.length) {
            const bar = state.bars[i];
            if (bar.levels) {
                // Fast Key Scan
                for (let k in bar.levels) {
                    const p = parseFloat(k);
                    if (p < minP) minP = p;
                    if (p > maxP) maxP = p;
                }
                hasVisibleData = true;
            }
        }
    }

    // If no visible bars (scrolled too far empty), use last known or global
    if (!hasVisibleData) {
        // Fallback to avoid crash
        minP = state.view.offsetY - 10;
        maxP = state.view.offsetY + 10;
    }

    if (minP !== Infinity && maxP !== -Infinity) {
        const midPrice = (minP + maxP) / 2;
        const priceRange = maxP - minP || 1;

        // Auto-Center
        state.view.offsetY = midPrice;

        // Auto-Scale Y (Fixes "Middle 10%" issue)
        // We want the range to occupy ~70% of screen height (Increased Buffer)
        const targetScale = (h * 0.70) / priceRange;

        // Clamp scale to prevent super zoom on single ticks
        // Min 10px per unit, Max 200?
        // Actually, if priceRange is 0.05, and h=1000, scale = 850/0.05 = 17000 (Huge!)
        // This is fine, we want to see that single tick huge.
        // But let's smooth it or just apply. 
        // For responsiveness, direct apply is best.

        state.view.scaleY = targetScale;
    }

    // Y axis: Middle of screen is state.view.offsetY
    const cy = h / 2;
    // Map price to integer pixel to avoid fuzzy text
    const priceToY = (price) => Math.floor(cy - (price - state.view.offsetY) * state.view.scaleY);

    // Draw Grid & Axes
    drawGrid(w, h, priceToY);

    // Draw Bars
    // Use integer x coordinates for crisp lines
    for (let i = startIndex; i <= endIndex; i++) {
        if (i < 0 || i >= state.bars.length) continue;

        const bar = state.bars[i];
        const x = Math.floor((i - state.view.endIndex) * state.view.scaleX + w - 150);

        // Optimize: Don't draw if off-screen (though startIndex handles X, we double check)
        if (x + state.view.scaleX < 0 || x > w) continue;

        drawFootprintBar(ctx, bar, x, state.view.scaleX, priceToY);
    }

    // 3. Draw Trades Layer (Overlay)
    drawTrades(ctx, priceToY, w, h);
}

function drawTrades(ctx, priceToY, w, h) {
    if (!state.trades || state.trades.length === 0) return;

    // Helper: Map TS to X
    // We need to find the index of the bar matching TS, or interpolate
    const getX = (ts) => {
        // Binary search or simple find? Optimization: simple fit
        // ts is ms. state.bars[].ts is sec usually? No, check backend.
        // run_merged: ts is in ms (start_ts * 1000). Trade ts is ms.
        // Wait, app.js logic uses `bar.ts` as key.

        // Exact match preferred
        let idx = -1;
        // Optimization: Bars are sorted.
        // Find index such that bars[i].ts <= ts < bars[i+1].ts
        // Since Footprint bars are discrete buckets, we align to the bucket start.

        // Simple scan (assuming array < 10000 items is fast enough)
        // or just find closest?
        // Trades ts might be EXACT execution time, unlike Bar Start Time.
        // So we project it onto the Time Axis defined by Bars.
        // X = (Index - EndIndex) * ScaleX.
        // We need fractional index if trade happened in middle of bar?
        // No, current rendering is pure Index based.
        // Let's match to the NEAREST bar.

        // Find closest bar index
        // Since sorted:
        let bestDist = Infinity;
        let bestI = -1;

        // Optimize: verify ts format
        if (!ts) return null;

        // Optimization: Binary search would be better but let's do linear for now
        // Or approx index if continuous? No, bars are non-linear time (hybrid).
        // Must search.

        for (let i = 0; i < state.bars.length; i++) {
            const dist = Math.abs(state.bars[i].ts - ts); // both ms?
            if (dist < bestDist) {
                bestDist = dist;
                bestI = i;
            }
        }

        if (bestI === -1) return null;

        // Only valid if reasonable proximity? (e.g. within 1 hour?)
        // If history is old and trade is new, it might not match.
        // But we loaded history for this symbol.

        return Math.floor((bestI - state.view.endIndex) * state.view.scaleX + w - 150);
    };

    ctx.lineWidth = 2;
    ctx.font = "bold 12px Inter";

    state.trades.forEach(t => {
        const ex = getX(t.entry_ts);
        const ey = priceToY(t.entry_price);

        if (ex === null) return; // Not visible/found

        const isLong = (t.side === "LONG" || t.side === "BUY");
        const color = isLong ? "#00ffff" : "#ff00ff"; // Cyan / Magenta

        // Draw Exit if closed
        if (t.status === "CLOSED" && t.exit_ts) {
            const xx = getX(t.exit_ts);
            const xy = priceToY(t.exit_price);

            if (xx !== null) {
                // Line
                ctx.beginPath();
                ctx.strokeStyle = color;
                ctx.setLineDash([5, 5]);
                ctx.moveTo(ex, ey);
                ctx.lineTo(xx, xy);
                ctx.stroke();
                ctx.setLineDash([]);

                // Exit Marker (X or Square)
                ctx.fillStyle = color;
                ctx.fillRect(xx - 4, xy - 4, 8, 8);
            }
        } else if (t.status === "OPEN") {
            // Draw line to current price?
            // Or just to right edge
            const xx = w - 150; // Current Live Bar X roughly
            const xy = priceToY(engine_last_ltp || t.entry_price); // Need LTP?
            // Just draw infinite line
            ctx.beginPath();
            ctx.strokeStyle = color;
            ctx.setLineDash([2, 5]);
            ctx.moveTo(ex, ey);
            ctx.lineTo(w, ey); // Horizontal line at Entry Price
            ctx.stroke();
            ctx.setLineDash([]);
        }

        // Draw Entry Marker (Triangle)
        ctx.fillStyle = color;
        ctx.beginPath();
        if (isLong) {
            // Up Triangle
            ctx.moveTo(ex, ey - 10);
            ctx.lineTo(ex - 6, ey + 2);
            ctx.lineTo(ex + 6, ey + 2);
        } else {
            // Down Triangle
            ctx.moveTo(ex, ey + 10);
            ctx.lineTo(ex - 6, ey - 2);
            ctx.lineTo(ex + 6, ey - 2);
        }
        ctx.fill();

        // Label
        ctx.fillStyle = "#fff";
        ctx.strokeText(t.side === "LONG" ? "L" : "S", ex - 4, ey + 40 * (isLong ? 1 : -1));
        ctx.fillText(t.side === "LONG" ? "L" : "S", ex - 4, ey + 40 * (isLong ? 1 : -1));
    });
}

function drawGrid(w, h, priceToY) {
    ctx.strokeStyle = '#21262d';
    ctx.fillStyle = '#c9d1d9'; // Brighter text color for visibility
    ctx.font = '11px Inter';
    ctx.lineWidth = 1;
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';

    // --- Y Axis (Price) ---
    // Determine useful step size based on scaleY
    // scaleY = pixels per unit price.
    // We want lines every ~50 pixels.
    // Price delta = 50 / scaleY
    const pxStepTarget = 50;
    const rawPriceStep = pxStepTarget / state.view.scaleY;

    // Snap to nice values (1, 0.5, 0.1, 0.05, etc)
    const mag = Math.pow(10, Math.floor(Math.log10(rawPriceStep)));
    let step = mag;
    if (rawPriceStep / mag > 5) step = mag * 5;
    else if (rawPriceStep / mag > 2) step = mag * 2;

    state.view.priceStep = step;

    // Find start and end price
    // Top price (y=0) -> price = offsetY + (cy - 0)/scaleY
    // Bottom price (y=h) -> price = offsetY + (cy - h)/scaleY
    const cy = h / 2;
    const topPrice = state.view.offsetY + cy / state.view.scaleY;
    const bottomPrice = state.view.offsetY - (h - cy) / state.view.scaleY;

    const startP = Math.floor(bottomPrice / step) * step;
    const endP = Math.ceil(topPrice / step) * step;

    ctx.beginPath();
    for (let p = startP; p <= endP; p += step) {
        const y = priceToY(p);
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        // Label
        ctx.fillText(p.toFixed(2), w - 5, y); // Draw label on right edge
    }
    ctx.stroke();

    // --- X Axis (Time) ---
    // Draw time labels at bottom
    // Every N bars
    // barWidth = scaleX
    // We want labels every ~100 pixels
    const barStep = Math.ceil(100 / state.view.scaleX);

    // Iterate visible bars based on the loop in draw()
    const visibleBarsCount = Math.ceil(w / state.view.scaleX) + 1;
    let endIndex = Math.floor(state.view.endIndex);
    let startIndex = endIndex - visibleBarsCount;

    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';

    for (let i = startIndex; i <= endIndex; i++) {
        if (i % barStep === 0 && i >= 0 && i < state.bars.length) {
            const bar = state.bars[i];
            const x = (i - state.view.endIndex) * state.view.scaleX + w - 50;

            // Tick mark
            ctx.beginPath();
            ctx.moveTo(x, h);
            ctx.lineTo(x, h - 5);
            ctx.stroke();

            // Label (Format TS)
            // TS is already in ms (from footprint_engine)
            const date = new Date(bar.ts);
            const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

            ctx.fillText(timeStr, x, h - 8);
        }
    }
}

// --- Volume Bubble Logic ---

function calculateVolumeStats() {
    const period = 200;
    // Extract recent volumes for efficiency? No, safer to recalc all for consistency if array changes.
    // Optimization: Only recalc if array length changed significantly? 
    // JS is fast enough for 5000 items.

    const volumes = state.bars.map(b => b.totalVol);

    for (let i = 0; i < state.bars.length; i++) {
        const start = Math.max(0, i - period + 1);
        const slice = volumes.slice(start, i + 1);
        const n = slice.length;

        if (n < 2) {
            state.bars[i].normVol = 0;
            continue;
        }

        const sum = slice.reduce((a, b) => a + b, 0);
        const mean = sum / n;
        const variance = slice.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / n;
        const stdev = Math.sqrt(variance);

        // Avoid division by zero
        state.bars[i].normVol = stdev === 0 ? 0 : (state.bars[i].totalVol / stdev);
    }
}

function getBubbleColor(norm) {
    // Logic:
    // < 1: Aqua (Low/Normal)
    // 1 - 3: Green
    // 3 - 5: Orange
    // > 5: Red

    if (norm < 1.0) return 'rgba(0, 255, 255, 0.3)'; // Aqua Transparent
    if (norm < 3.0) return 'rgba(0, 255, 0, 0.5)';   // Green Semi
    if (norm < 5.0) return 'rgba(255, 165, 0, 0.6)'; // Orange
    return 'rgba(255, 0, 0, 0.8)';                   // Red Solid
}

function drawFootprintBar(ctx, bar, x, width, priceToY) {
    if (!bar.levels) return;

    // --- Draw Volume Bubble (Bottom) ---
    if (bar.normVol > 0.5) { // Threshold to show bubble
        const cx = x - width / 2;
        const cy = state.canvasSize.h - 25; // 25px from bottom (above time labels)

        // Radius based on normVol
        // Min radius 2, Max radius width/2
        // NormVol 1 -> 3px
        // NormVol 5 -> Max
        let r = Math.min(width / 2 - 2, 3 + (bar.normVol * 2));
        r = Math.max(2, r); // Safety

        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fillStyle = getBubbleColor(bar.normVol);
        ctx.fill();

        // Optional: Border for extreme
        if (bar.normVol > 5.0) {
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 1;
            ctx.stroke();
        }
    }

    // Layout Config
    const padding = 2;
    const deltaBarWidth = width * 0.25; // 25% for Delta Profile
    const textWidth = width - deltaBarWidth;
    const midX = x - deltaBarWidth - (textWidth / 2); // Center of text area
    const cellH = Math.max(14, state.view.scaleY);

    // Pre-calc max delta for scaling histogram & POC
    let maxDelta = 1;
    let maxLevelVol = 0;
    let pocPrice = null;

    Object.entries(bar.levels).forEach(([pStr, v]) => {
        const d = Math.abs((v.ask || 0) - (v.bid || 0));
        if (d > maxDelta) maxDelta = d;

        const tot = (v.ask || 0) + (v.bid || 0);
        if (tot > maxLevelVol) {
            maxLevelVol = tot;
            pocPrice = parseFloat(pStr);
        }
    });

    // Separator Line (Vertical) between Bid/Ask and Delta
    ctx.beginPath();
    ctx.strokeStyle = '#333';
    ctx.moveTo(x - deltaBarWidth, 0);
    ctx.lineTo(x - deltaBarWidth, state.canvasSize.h);
    ctx.stroke();

    // Iterate levels
    Object.entries(bar.levels).forEach(([pStr, val]) => {
        const price = parseFloat(pStr);
        const y = priceToY(price);

        // Culling
        if (y < -cellH || y > state.canvasSize.h + cellH) return;

        const bid = val.bid || 0;
        const ask = val.ask || 0;
        const delta = ask - bid;
        const total = bid + ask;

        // --- 1. Draw Delta Profile (Background Layer) ---
        const barLen = (Math.abs(delta) / maxDelta) * (deltaBarWidth - 4);
        const barH = cellH - 2;
        // Align delta bar to the LEFT of the strip (colloquial usage)
        const stripX = x - deltaBarWidth + padding;

        ctx.fillStyle = delta > 0 ? '#1e3a25' : '#3a1e1e'; // Dark BG
        ctx.fillRect(stripX, y - barH / 2, deltaBarWidth - padding * 2, barH);

        ctx.fillStyle = delta > 0 ? '#4ade80' : '#ff6b6b'; // Bright Bar
        ctx.fillRect(stripX, y - barH / 2, Math.max(1, barLen), barH);

        // --- 2. Draw Text Backgrounds (Imbalance / POC) ---
        // Imbalance Logic
        const isBidImbalance = bid > ask * 3 && bid > 5;
        const isAskImbalance = ask > bid * 3 && ask > 5;
        const isPOC = (price === pocPrice);

        // POC Highlight (Yellow Box Outline or BG)
        if (isPOC) {
            ctx.strokeStyle = '#f4e58e57'; // Gold
            ctx.lineWidth = 2;
            ctx.strokeRect(x - width + 2, y - cellH / 2 + 1, textWidth - 4, cellH - 2);
            ctx.fillStyle = '#7e7d7c6f';
            ctx.fillRect(x - width + 2, y - cellH / 2 + 1, textWidth - 4, cellH - 2);
        }

        // --- 3. Draw Text (Foreground Layer) ---
        if (state.view.scaleY > 12) {
            ctx.font = '11px JetBrains Mono';
            ctx.textBaseline = 'middle';

            // Bid (Left)
            ctx.textAlign = 'right';
            ctx.fillStyle = isBidImbalance ? '#ff444470' : '#888';
            if (isBidImbalance) ctx.font = 'bold 11px JetBrains Mono';
            ctx.fillText(bid, midX - 4, y);
            if (isBidImbalance) ctx.font = '11px JetBrains Mono';

            // Divider
            ctx.fillStyle = '#444';
            ctx.fillRect(midX - 0.5, y - 4, 1, 8);

            // Ask (Right)
            ctx.textAlign = 'left';
            ctx.fillStyle = isAskImbalance ? '#00ff0084' : '#888';
            if (isAskImbalance) ctx.font = 'bold 11px JetBrains Mono';
            ctx.fillText(ask, midX + 4, y);
        }
    });

    // Draw Box around the whole bar
    ctx.lineWidth = 1;
    ctx.strokeStyle = '#222';
    ctx.strokeRect(x - width, 0, width, state.canvasSize.h);
}

function drawDOM() {
    // Basic DOM drawing
    domCtx.clearRect(0, 0, elements.domCanvas.width, elements.domCanvas.height);
    domCtx.font = "12px Inter";

    let y = 30;
    const center = elements.domCanvas.width / 2;

    // Asks (Top, Red)
    // Sort asks (ascending price)
    const asks = Object.entries(state.dom.asks || {}).sort((a, b) => parseFloat(a[0]) - parseFloat(b[0])).slice(0, 20);
    // Reverse for display (highest price at top? No, lowest ask is best price, should be near center?)
    // Standard DOM: Price Ladder. High prices at top.
    // So Asks (High prices) -> Bids (Low prices).

    // Just simple list for now as per previous impl, but cleaner
    domCtx.fillStyle = "#8b949e";
    domCtx.fillText("ASKS", 10, 15);

    asks.reverse().forEach(([p, q]) => {
        domCtx.fillStyle = "#ff6b6b";
        domCtx.textAlign = "right";
        domCtx.fillText(p, center - 10, y);
        domCtx.textAlign = "left";
        domCtx.fillStyle = "#c9d1d9";
        domCtx.fillText(q, center + 10, y);
        y += 16;
    });

    y += 20;
    domCtx.fillStyle = "#8b949e";
    domCtx.fillText("BIDS", 10, y - 5);

    const bids = Object.entries(state.dom.bids || {}).sort((a, b) => parseFloat(b[0]) - parseFloat(a[0])).slice(0, 20);
    bids.forEach(([p, q]) => {
        domCtx.fillStyle = "#4ade80";
        domCtx.textAlign = "right";
        domCtx.fillText(p, center - 10, y);
        domCtx.textAlign = "left";
        domCtx.fillStyle = "#c9d1d9";
        domCtx.fillText(q, center + 10, y);
        y += 16;
    });
}


function setOverlay(msg) {
    elements.msgOverlay.textContent = msg || '';
}

// Start
init();
