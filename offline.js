'use strict';
// CSP: no inline handlers/scripts (script-src 'self')
document.getElementById('retry').addEventListener('click', () => { location.href = './'; });
addEventListener('online', () => { location.href = './'; });
