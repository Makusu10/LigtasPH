const fs = require('fs');

let lines = fs.readFileSync('server.ts', 'utf8').split('\n');
let start = -1;
let end = -1;

for (let i = 0; i < lines.length; i++) {
  if (lines[i].includes('import { CRITICAL_FACILITIES }')) {
    start = i;
  }
  if (lines[i].includes('// Fallback to avoid breaking UI if Overpass is down/rate-limited')) {
    end = i + 5; // to cover the whole old route
  }
}

if (start !== -1 && end !== -1) {
  // we actually want to delete from line 290 to 330
  // let's do it by reading lines 290 to 331
}
