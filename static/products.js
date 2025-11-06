(function(){
  console.log('[PRODUCTS.JS] Professional UI v3.0 loaded');

  // Track stock updates
  const stockCache = new Map();

  function updateConnectionStatus(status) {
    let statusEl = document.querySelector('.connection-status');
    if (!statusEl) {
      statusEl = document.createElement('div');
      statusEl.className = 'connection-status';
      document.body.appendChild(statusEl);
    }

    statusEl.className = 'connection-status ' + status;
    const text = {
      'connected': '✓ Live Updates Active',
      'connecting': '⟳ Connecting...',
      'disconnected': '✗ Disconnected'
    };
    statusEl.textContent = text[status] || status;
  }

  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.style.animation = 'toastSlide 0.3s ease reverse';
      setTimeout(() => toast.remove(), 300);
    }, 2000);
  }

  // Live update stock values on the products grid via SSE
  function startSSE(){
    try {
      const es = new EventSource('/events');
      console.log('[SSE] Connecting to real-time updates...');
      updateConnectionStatus('connecting');

      es.addEventListener('open', () => {
        console.log('[SSE] ✅ Connected - Real-time stock updates active');
        updateConnectionStatus('connected');
        showToast('Real-time updates connected!', 'success');
      });

      es.addEventListener('stock', (ev) => {
        console.log('[SSE] Stock update received:', ev.data);

        let payload = null;
        try {
          payload = JSON.parse(ev.data);
        } catch (_) {
          payload = { stock: ev.data };
        }

        if (!payload || typeof payload.stock === 'undefined') {
          console.warn('[SSE] Invalid payload');
          return;
        }

        const pid = payload.product_id;
        const value = payload.stock;

        // Update the stock display for this product
        if (pid != null) {
          const stockEl = document.querySelector(`.stock-value[data-product-id="${pid}"]`);
          console.log(`[SSE] Looking for stock element with product_id=${pid}:`, stockEl);

          if (stockEl) {
            const oldValue = parseInt(stockEl.textContent) || 0;
            const newValue = parseInt(value);
            const delta = newValue - oldValue;

            // Cache previous value
            stockCache.set(pid, oldValue);

            // Add animation
            stockEl.classList.add('updating');
            setTimeout(() => stockEl.classList.remove('updating'), 500);

            // Update value
            stockEl.textContent = value;

            // Update color based on stock level
            stockEl.className = 'stock-value';
            stockEl.setAttribute('data-product-id', pid);

            if (newValue === 0) {
              stockEl.classList.add('out');
            } else if (newValue < 20) {
              stockEl.classList.add('low');
            }

            console.log(`[SSE] ✅ Product ${pid} stock updated: ${oldValue} → ${newValue} (${delta >= 0 ? '+' : ''}${delta})`);

            // Show toast notification
            showToast(`Product ${pid}: Stock ${newValue} (${delta >= 0 ? '+' : ''}${delta})`,
                     delta < 0 ? 'warning' : 'success');

            // Log data source
            console.log(`[DATA SOURCE] Redis Pub/Sub → SSE → UI`);
          } else {
            console.warn(`[SSE] ⚠️ No element found for product ${pid}`);
          }
        } else {
          console.warn('[SSE] ⚠️ No product_id in payload');
        }
      });

      es.onerror = (e) => {
        console.error('[SSE] Error:', e, 'readyState:', es.readyState);

        if (es.readyState === EventSource.CONNECTING) {
          console.log('[SSE] Reconnecting...');
          updateConnectionStatus('connecting');
        } else if (es.readyState === EventSource.CLOSED) {
          console.error('[SSE] ❌ Connection closed');
          updateConnectionStatus('disconnected');
          showToast('Connection lost. Refresh to reconnect.', 'error');
        }
      };
    } catch (e) {
      console.error('[SSE] ❌ Failed to initialize:', e);
      updateConnectionStatus('disconnected');
    }
  }

  // Add loading skeleton on page load
  function showInitialLoading() {
    const grid = document.querySelector('.products-grid');
    if (!grid) return;

    grid.querySelectorAll('.stock-value').forEach(el => {
      const loader = document.createElement('span');
      loader.className = 'loading';
      loader.style.marginLeft = '0.5rem';
      el.appendChild(loader);

      setTimeout(() => loader.remove(), 1000);
    });
  }

  // Add data source indicators
  function addDataSourceIndicators() {
    const stockElements = document.querySelectorAll('.stock-value');
    stockElements.forEach(el => {
      const badge = document.createElement('span');
      badge.className = 'data-source-badge cache-hit';
      badge.textContent = 'LIVE';
      badge.title = 'Real-time updates via Redis';
      badge.style.marginLeft = '0.5rem';
      badge.style.fontSize = '0.65rem';
      badge.style.padding = '0.15rem 0.4rem';
      el.parentElement.appendChild(badge);
    });
  }

  // Initialize
  console.log('[PRODUCTS.JS] Initializing...');
  showInitialLoading();
  setTimeout(() => {
    addDataSourceIndicators();
    startSSE();
  }, 100);

  console.log('[PRODUCTS.JS] ✓ Ready for real-time updates');
})();

