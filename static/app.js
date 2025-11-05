(function(){
  const els = {
    name: document.getElementById('product-name'),
    price: document.getElementById('product-price'),
    stock: document.getElementById('product-stock'),
    qty: document.getElementById('quantity'),
    form: document.getElementById('purchase-form'),
    result: document.getElementById('result'),
  };

  async function fetchStock() {
    try {
      const res = await fetch('/stock');
      const data = await res.json();
      if (res.ok) {
        els.name.textContent = data.name + ' (ID ' + data.product_id + ')';
        els.price.textContent = Number(data.price).toFixed(2);
        els.stock.textContent = data.stock;
      } else {
        els.result.textContent = JSON.stringify(data, null, 2);
      }
    } catch (e) {
      console.error(e);
    }
  }

  function startSSE() {
    try {
      const es = new EventSource('/events');
      es.addEventListener('stock', (ev) => {
        try {
          // our server publishes the new stock as plain text number
          const value = ev.data;
          els.stock.textContent = value;
        } catch (_) {}
      });
      es.onerror = (e) => {
        console.warn('SSE error', e);
      };
    } catch (e) {
      console.warn('SSE not supported', e);
    }
  }

  els.form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const qty = parseInt(els.qty.value || '1', 10);
    els.result.textContent = 'Submitting...';
    try {
      const res = await fetch('/purchase', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quantity: qty })
      });
      const data = await res.json();
      els.result.textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      els.result.textContent = String(err);
    }
  });

  fetchStock();
  startSSE();
})();

