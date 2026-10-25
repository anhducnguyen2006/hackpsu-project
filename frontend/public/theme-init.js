// Blocking head script: resolve the palette before stylesheets or React can paint.
(function () {
  var theme;
  try { theme = localStorage.getItem('dataopedia-theme'); } catch (_) {}
  if (theme !== 'light' && theme !== 'dark') {
    theme = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  document.documentElement.style.backgroundColor = theme === 'dark' ? '#090907' : '#DDE3E8';
  document.querySelector('meta[name="theme-color"]').setAttribute('content', theme === 'dark' ? '#090907' : '#DDE3E8');
}());
