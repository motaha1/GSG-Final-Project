(function(){
  const els = {
    name: document.getElementById('product-name'),
    price: document.getElementById('product-price'),
    stock: document.getElementById('product-stock'),
    qty: document.getElementById('quantity'),
    form: document.getElementById('purchase-form'),
    result: document.getElementById('result'),
  };

  // Get product ID from meta tag on single product page
  const metaProductId = document.querySelector('meta[name="product-id"]');
  let currentProductId = metaProductId ? parseInt(metaProductId.getAttribute('content'), 10) : null;

  // Track last known stock to print deltas
  let lastStock = null;
  let isLoading = false;

  // UI Helper Functions
  function showLoading(element) {
    const loader = document.createElement('span');
    loader.className = 'loading';
    loader.id = 'inline-loader';
    element.appendChild(loader);
  }

  function hideLoading() {
    const loader = document.getElementById('inline-loader');
    if (loader) loader.remove();
  }

  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.style.animation = 'toastSlide 0.3s ease reverse';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  function addDataSourceBadge(text, source) {
    let badge = document.querySelector('.data-source-badge');
    if (!badge) {
      badge = document.createElement('span');
      badge.className = 'data-source-badge';
      els.name.appendChild(badge);
    }

    badge.className = 'data-source-badge ' + source;
    badge.textContent = source.toUpperCase();

    // Add explanatory text
    const tooltip = {
      'redis': 'Cached (Fast)',
      'db': 'Database',
      'cache-hit': 'Cache Hit'
    };
    badge.title = tooltip[source] || source;
  }

  function updateConnectionStatus(status) {
    let statusEl = document.querySelector('.connection-status');
    if (!statusEl) {
      statusEl = document.createElement('div');
      statusEl.className = 'connection-status';
      document.body.appendChild(statusEl);
    }

    statusEl.className = 'connection-status ' + status;
    const text = {
      'connected': 'SSE Connected',
      'connecting': 'Connecting...',
      'disconnected': 'Disconnected'
    };
    statusEl.textContent = text[status] || status;
  }

  function logMessage(message, type = 'info', data = null) {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;

    const timestamp = new Date().toLocaleTimeString();
    let content = `[${timestamp}] ${message}`;

    if (data) {
      content += '\n' + JSON.stringify(data, null, 2);
    }

    entry.textContent = content;
    els.result.appendChild(entry);
    els.result.scrollTop = els.result.scrollHeight;
  }

  // Add a tiny fetch logger used by our calls
  async function logFetch(url, options = {}) {
    const method = (options && options.method) || 'GET';
    const body = options && options.body ? options.body : undefined;

    logMessage(`${method} ${url}`, 'info');
    console.log('[HTTP]', method, url, body || '');

    const startTime = performance.now();
    const res = await fetch(url, options);
    const duration = (performance.now() - startTime).toFixed(0);

    console.log('[HTTP RES]', res.status, res.statusText, url, `(${duration}ms)`);
    logMessage(`Response: ${res.status} ${res.statusText} (${duration}ms)`,
               res.ok ? 'success' : 'error');

    return res;
  }

  async function fetchStock() {
    if (!els.name) return; // Not on product page

    try {
      showLoading(els.name);
      logMessage('Fetching product stock...', 'info');

      const res = await logFetch('/stock' + (currentProductId ? ('?product_id=' + currentProductId) : ''));
      const data = await res.json();
      console.log('[HTTP JSON] /stock', data);

      if (res.ok) {
        els.name.textContent = data.name + ' (ID ' + data.product_id + ')';
        els.price.textContent = '$' + Number(data.price).toFixed(2);
        els.stock.textContent = data.stock;

        // Add data source badge
        addDataSourceBadge(data.name, 'redis');

        // Color code stock
        const stockEl = els.stock;
        stockEl.className = 'stock-value';
        if (data.stock === 0) {
          stockEl.classList.add('out');
        } else if (data.stock < 20) {
          stockEl.classList.add('low');
        }

        const parsed = Number(data.stock);
        if (!Number.isNaN(parsed)) lastStock = parsed;
        currentProductId = data.product_id;

        logMessage(`Product loaded: ${data.name}`, 'success', {
          source: 'Redis/Cache',
          stock: data.stock,
          price: data.price
        });

        showToast(`Product loaded: ${data.name}`, 'success');
      } else {
        logMessage('Error fetching stock', 'error', data);
        showToast('Failed to load product', 'error');
      }
    } catch (e) {
      console.error(e);
      logMessage('Fetch /stock failed: ' + e.message, 'error');
      showToast('Connection error', 'error');
    } finally {
      hideLoading();
    }
  }

  // SSE management: keep waiters for next stock event
  const sse = { es: null, waiters: [] };

  function waitNextStockEvent(timeoutMs = 10000) {
    return new Promise((resolve, reject) => {
      let wrapped = null;
      const timer = setTimeout(() => {
        const idx = sse.waiters.indexOf(wrapped);
        if (idx >= 0) sse.waiters.splice(idx, 1);
        reject(new Error('Timed out waiting for SSE stock event'));
      }, timeoutMs);
      wrapped = (data) => {
        clearTimeout(timer);
        resolve(data);
      };
      sse.waiters.push(wrapped);
    });
  }

  function startSSE() {
    try {
      const es = new EventSource('/events');
      sse.es = es;

      es.addEventListener('open', () => {
        console.log('[SSE] connected');
        updateConnectionStatus('connected');
        logMessage('SSE connection established', 'success');
      });

      es.addEventListener('stock', (ev) => {
        try {
          // Expect JSON: { product_id, stock } but also support plain number
          let payload = null;
          try { payload = JSON.parse(ev.data); } catch (_) { payload = { stock: ev.data }; }
          const pid = payload.product_id;
          const value = payload.stock;

          if (currentProductId && pid && Number(pid) !== Number(currentProductId)) {
            // Different product; ignore on single-product page
            return;
          }

          // Add updating animation
          if (els.stock) {
            els.stock.classList.add('updating');
            setTimeout(() => els.stock.classList.remove('updating'), 500);
            els.stock.textContent = value;

            // Update stock color
            els.stock.className = 'stock-value';
            if (value === 0) {
              els.stock.classList.add('out');
            } else if (value < 20) {
              els.stock.classList.add('low');
            }
          }

          const next = Number(value);
          const hadPrev = lastStock !== null && !Number.isNaN(lastStock);
          const delta = hadPrev && !Number.isNaN(next) ? (next - lastStock) : null;
          lastStock = !Number.isNaN(next) ? next : lastStock;

          const msg = delta === null
            ? `Stock updated: ${value}${pid ? ` for product ${pid}` : ''}`
            : `Stock changed: ${value} (${delta >= 0 ? '+' : ''}${delta})${pid ? ` for product ${pid}` : ''}`;

          console.log('[SSE]', msg);
          logMessage(msg, delta && delta < 0 ? 'warning' : 'info', {
            source: 'Redis Pub/Sub',
            product_id: pid,
            new_stock: value,
            change: delta
          });

          // Show toast for stock changes
          if (delta !== null) {
            showToast(msg, delta < 0 ? 'warning' : 'success');
          }

          const waiter = sse.waiters.shift();
          if (waiter) waiter(value);
        } catch (e) {
          console.error(e);
        }
      });

      es.onerror = (e) => {
        if (es.readyState === EventSource.CONNECTING || es.readyState === EventSource.OPEN) {
          console.log('[SSE] reconnecting/keeping connection alive');
          updateConnectionStatus('connecting');
        } else if (es.readyState === EventSource.CLOSED) {
          console.error('[SSE] closed', e);
          updateConnectionStatus('disconnected');
          logMessage('SSE connection closed', 'error');
        } else {
          console.warn('[SSE] error', e);
          updateConnectionStatus('connecting');
        }
      };
    } catch (e) {
      console.warn('SSE not supported', e);
      logMessage('SSE not supported: ' + e.message, 'warning');
    }
  }

  if (els.form) {
    els.form.addEventListener('submit', async (e) => {
      e.preventDefault();

      if (isLoading) return;

      const qty = parseInt(els.qty.value || '1', 10);
      const btn = els.form.querySelector('button');

      try {
        isLoading = true;
        btn.disabled = true;
        btn.classList.add('loading');
        btn.textContent = 'Processing...';

        logMessage(`Submitting purchase order`, 'info', {
          quantity: qty,
          product_id: currentProductId
        });

        const payload = { quantity: qty };
        if (currentProductId) {
          payload.product_id = currentProductId;
        }

        const res = await logFetch('/purchase', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const data = await res.json();
        console.log('[BUY] response', data);

        if (res.ok) {
          logMessage('Purchase order submitted successfully', 'success', data);
          showToast('Order submitted! Processing...', 'success');

          logMessage('Order sent to Kafka', 'info');
          logMessage('Waiting for payment processing...', 'info');

          // After a successful publish to Kafka, the worker will update stock and emit SSE.
          // Wait up to 10s for the next SSE stock event and print it.
          try {
            const next = await waitNextStockEvent(10000);
            console.log('[SSE] next after purchase', next);
            logMessage(`Stock updated from DB: ${next}`, 'success', {
              source: 'Database -> Redis -> SSE',
              new_stock: next
            });
            showToast(`Purchase complete! Stock: ${next}`, 'success');
          } catch (timeoutErr) {
            console.warn('[SSE] no event within 10s');
            logMessage('No stock update received (check worker logs)', 'warning');
            showToast('Order submitted but stock update delayed', 'warning');
          }
        } else {
          logMessage('Purchase failed', 'error', data);
          showToast('Purchase failed: ' + (data.error || 'Unknown error'), 'error');
        }
      } catch (err) {
        console.error('[BUY] failed', err);
        logMessage('Purchase request failed: ' + err.message, 'error');
        showToast('Network error during purchase', 'error');
      } finally {
        isLoading = false;
        btn.disabled = false;
        btn.classList.remove('loading');
        btn.textContent = 'Buy Now';
      }
    });
  }

  // Initialize
  fetchStock();
  startSSE();
})();

