const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
const start = html.indexOf('    function inferredStorySlab(');
const end = html.indexOf('    function addRoom3D(', start);
assert(start >= 0 && end > start);
const context = {};
vm.createContext(context);
vm.runInContext(html.slice(start, end), context);

const floor = {id: 'ground', name: 'Ground', color: '#0f766e'};
const boundary = {x: -12.5, y: -2.5, w: 39, h: 35};
assert.equal(context.inferredStorySlab({...floor, exteriorOnly: true}, [], [], boundary), null);
assert.equal(context.inferredStorySlab(floor, [], [], null), null);
const fallback = context.inferredStorySlab(floor, [], [], boundary);
for (const key of ['x', 'y', 'w', 'h']) assert.equal(fallback[key], boundary[key]);
assert.equal(fallback.structuralSlab, true);
const room = {type: 'room', x: 2, y: 3, w: 4, h: 5};
const enclosed = context.inferredStorySlab(floor, [room], [], boundary);
for (const key of ['x', 'y', 'w', 'h']) assert.equal(enclosed[key], room[key]);
console.log('Exterior-only exclusion and ordinary story slab fallbacks passed.');
