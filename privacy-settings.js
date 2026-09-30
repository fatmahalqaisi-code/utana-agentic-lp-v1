(() => {
  'use strict';
  const key = 'utana.privacy.v1';
  const lifetime = 180 * 24 * 60 * 60 * 1000;
  const policyUrl = new URL('privacy.html', document.currentScript.src).href;
  let saved = null;
  try {
    const value = JSON.parse(localStorage.getItem(key));
    if (value?.version === 1 && value.necessary === true && Number.isFinite(value.savedAt) && value.savedAt <= Date.now() && Date.now() - value.savedAt < lifetime) saved = value;
  } catch (_) { /* Storage may be blocked or contain an old value. */ }

  const panel = document.createElement('dialog');
  panel.className = 'privacy-panel';
  panel.setAttribute('aria-labelledby', 'privacy-title');
  panel.innerHTML = `
    <div class="privacy-heading"><p class="privacy-eyebrow">UTANA / YOUR PRIVACY</p><button type="button" class="privacy-close" aria-label="Close privacy settings">×</button></div>
    <h2 id="privacy-title">Your privacy choices</h2>
    <p>We don’t use analytics or advertising cookies. We save your privacy choice in this browser for 180 days so you don’t have to choose on every visit.</p>
    <p>Read our <a href="${policyUrl}">privacy notice</a> for details about fonts, hosting, and enquiries. You can reopen these settings from any page footer.</p>
    <div class="privacy-categories" hidden>
      <div class="privacy-category"><div><strong>Necessary</strong><p>Remembers this privacy choice on your device.</p></div><label class="privacy-switch"><input type="checkbox" checked disabled aria-label="Necessary storage, always on"><span aria-hidden="true"></span><small>Always on</small></label></div>
      <div class="privacy-category"><div><strong>Personalisation</strong><p>No personalisation cookies or saved visitor profiles.</p></div><label class="privacy-switch"><input type="checkbox" disabled aria-label="Personalisation, not used"><span aria-hidden="true"></span><small>Not used</small></label></div>
      <div class="privacy-category"><div><strong>Statistics</strong><p>No analytics trackers are installed.</p></div><label class="privacy-switch"><input type="checkbox" disabled aria-label="Statistics, not used"><span aria-hidden="true"></span><small>Not used</small></label></div>
      <div class="privacy-category"><div><strong>Marketing</strong><p>No advertising pixels or marketing cookies.</p></div><label class="privacy-switch"><input type="checkbox" disabled aria-label="Marketing, not used"><span aria-hidden="true"></span><small>Not used</small></label></div>
      <p class="privacy-detail">Only necessary storage is currently used. Accepting all does not authorise future tracking services.</p>
    </div>
    <div class="privacy-actions"><button type="button" data-choice="accept">Accept all</button><button type="button" data-choice="reject">Reject optional</button><button type="button" data-manage>Manage settings</button><button type="button" data-choice="selected" hidden>Save preferences</button></div>
    <p class="privacy-error" role="status"></p>`;
  document.body.append(panel);
  const categories = panel.querySelector('.privacy-categories');
  const manage = panel.querySelector('[data-manage]');
  const selected = panel.querySelector('[data-choice="selected"]');
  let returnFocus;
  function showDetails(details) {
    categories.hidden = !details;
    manage.hidden = details;
    selected.hidden = !details;
  }
  function open(details) {
    returnFocus = document.activeElement;
    showDetails(details);
    panel.querySelector('.privacy-error').textContent = '';
    panel.showModal();
  }
  panel.querySelector('.privacy-close').addEventListener('click', () => panel.close());
  panel.addEventListener('close', () => { if (returnFocus instanceof HTMLElement) returnFocus.focus({preventScroll:true}); });
  manage.addEventListener('click', () => { showDetails(true); selected.focus(); });
  panel.querySelectorAll('[data-choice]').forEach(button => button.addEventListener('click', () => {
    saved = {version:1, necessary:true, personalisation:false, statistics:false, marketing:false, savedAt:Date.now()};
    try { localStorage.setItem(key, JSON.stringify(saved)); }
    catch (_) {
      panel.querySelector('.privacy-error').textContent = 'Your browser could not save this choice. Optional tracking remains off. You can close this panel, but it may appear on your next visit.';
      return;
    }
    panel.close();
  }));
  const footer = document.querySelector('footer');
  if (footer) {
    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'privacy-settings-link';
    trigger.textContent = 'Cookie settings';
    trigger.addEventListener('click', () => open(true));
    (footer.querySelector('.footer-bottom') || footer).append(trigger);
  }
  if (!saved) open(false);
})();
