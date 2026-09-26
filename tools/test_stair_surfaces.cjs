const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
const context = { clamp: (v, a, b) => Math.min(b, Math.max(a, v)), state: { wallHeight: 2.79, floors: [{id:'lower'}, {id:'upper'}], stairs: [] } };
vm.createContext(context);
for (const [start, end] of [
  ['stairPlanRuns', 'drawStairSteps'], ['stairHolesForSlab', 'addSlabPieces3D'], ['slabRectPolygon', 'floorTexture'],
  ['addRoom3D', 'stairHolesForSlab']
]) {
  const a = html.indexOf(`    function ${start}(`), b = html.indexOf(`    function ${end}(`, a);
  assert(a >= 0 && b > a);
  vm.runInContext(html.slice(a, b), context);
}
const close = (a, b) => assert(Math.abs(a - b) < 1e-7, `${a} != ${b}`);
const stair = { x: 4, y: 3, w: 2.35, h: 4.69, landing: .95, shape: 'turned', turn: 'right', floorId: 'lower' };
const room = { x: -10, y: -10, w: 30, h: 30 };
const area = pieces => pieces.reduce((sum, p) => sum + (p.polygon ? context.slabPolygonArea(p.polygon) : p.w * p.h), 0);
const expected = .95 * (4.69 + 2.35 - .95);
for (const turn of ['left', 'right']) for (const rotation of [0, 90, 180, 270, -90, 33]) {
  const current = {...stair, turn, rotation};
  context.state.stairs = [current];
  const pieces = context.stairFootprintPieces(current);
  close(area(pieces), expected);
  const holes = context.stairHolesForSlab(room, {id:'upper'}, 'below');
  close(area(holes), expected);
  close(area(context.stairHolesForSlab(room, {id:'lower'}, 'current')), expected);
  assert.equal(context.stairHolesForSlab(room, {id:'lower'}, 'below').length, 0);
  assert.equal(context.stairHolesForSlab(room, {id:'upper'}, 'current').length, 0);
  let remainder = [context.slabRectPolygon(room)];
  for (const p of pieces) remainder = remainder.flatMap(poly => context.subtractConvexSlabHole(poly, p.polygon || context.slabRectPolygon(p)));
  close(remainder.reduce((s, p) => s + context.slabPolygonArea(p), 0), room.w * room.h - expected);
}
const rotated = context.stairFootprintPieces({...stair, rotation:90});
const minX = Math.min(...rotated.map(p=>p.x)), maxX = Math.max(...rotated.map(p=>p.x+p.w));
close(maxX-minX, stair.h);
close((minX+maxX)/2, stair.x+stair.w/2);

const custom = {...stair, w:4, h:3, cadRuns:[
  {x:0, y:2/3, w:.75, h:1/3, dir:'x'},
  {x:.75, y:0, w:.25, h:2/3, dir:'z', reverse:true}
], cadLanding:{x:.75,y:2/3,w:.25,h:1/3}};
assert(context.validCadStair(custom));
close(area(context.stairFootprintPieces(custom)), 6);
close(context.stairPlanRuns(custom)[0].w, 3);
assert(context.stairPlanRuns(custom)[1].reverse);
assert(!context.validCadStair({...custom, cadLanding:{x:NaN,y:0,w:1,h:1}}));
const plan = JSON.parse(fs.readFileSync(path.join(__dirname, '../plans/architect-alt-4-v2.json'), 'utf8'));
const upper = plan.stairs.find(stair => stair.floorId.endsWith('-living'));
assert(context.validCadStair(upper));
assert.equal(upper.shape,'uturn');
const upperPieces = context.stairFootprintPieces(upper);
assert(Math.abs(area(upperPieces)-(.85*2.17+.85*1.08+1.8*.85))<1e-6);
const shaft={x:5.9106,y:1.6831,w:1,h:1.5};
assert(upperPieces.every(p=>p.x+p.w<=shaft.x || p.x>=shaft.x+shaft.w || p.y+p.h<=shaft.y || p.y>=shaft.y+shaft.h));

// An opening crossing the slab edge must cut only its intersection.
const square = context.slabRectPolygon({x:0,y:0,w:2,h:2});
const diamond = [{x:1,y:-1},{x:3,y:1},{x:1,y:3},{x:-1,y:1}];
close(context.subtractConvexSlabHole(square, diamond).reduce((s,p)=>s+context.slabPolygonArea(p),0),0);
const cut = context.slabRectPolygon({x:1,y:-1,w:2,h:2});
close(context.subtractConvexSlabHole(square, cut).reduce((s,p)=>s+context.slabPolygonArea(p),0),3);

const surfaces = [];
Object.assign(context, { viewVisible: v=>v==='floor', colorToHex:v=>v, opacityForView:v=>v,
  storyCeilingElevation:()=>3, addSlabPieces3D:(...args)=>surfaces.push(args[8]), itemColor:()=>0, itemOpacity:()=>1 });
context.state.stairs = [];
context.addRoom3D({...room, type:'space', structuralSlab:true, ceiling:false}, {id:'lower',elevation:0}, []);
assert.deepEqual(surfaces, ['floor']);
surfaces.length = 0;
context.addRoom3D({...room, type:'space', structuralSlab:true}, {id:'lower',elevation:0}, []);
assert.deepEqual(surfaces, ['floor','ceiling']);
const slabCalls = [];
context.addSlabPieces3D = (...args) => slabCalls.push(args);
context.storyCeilingElevation = () => 3.14;
context.addRoom3D({...room, type:'space', structuralSlab:true}, {id:'lower',elevation:0}, []);
const ceiling = slabCalls.find(args => args[8] === 'ceiling');
close(ceiling[1], (2.79 + 3.14) / 2);
close(ceiling[2], .35);
console.log('Stair rotations, exact cutout areas, CAD runs, edge clipping, story ownership and outdoor ceilings passed.');
