const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'pdf_renders/alt4-v2');
const plan = JSON.parse(fs.readFileSync(path.join(root, 'plans/architect-alt-4-v2.json'), 'utf8'));
const planItem = id => [...plan.elements, ...plan.openings].find(item => item.id === `architect-alt-4-v2-${id}`);
assert(planItem('ground-assembly-guest-toilet-sink').height >= .9);
assert(planItem('ground-assembly-salon-exterior-wall-television').elevation >= .85);
for (const id of ['ground-window-gap-7', 'ground-window-gap-9', 'living-window-gap-13']) {
  const opening = planItem(id);
  assert.equal(opening.sill, 0, `${id} must reach the floor`);
  assert(opening.height >= 2.5, `${id} must reach the ceiling`);
}
assert.equal(planItem('ground-window-gap-7').openingStyle, 'sliding');
assert.equal(planItem('ground-window-gap-9').x, planItem('living-window-gap-13').x);
assert.equal(planItem('ground-window-gap-9').y, planItem('living-window-gap-13').y);
for (const id of [
  'basement-basin-east-mirror', 'basement-basin-west-mirror', 'ground-guest-toilet-mirror',
  'living-master-bathroom-mirror', 'living-bathroom-mirror', 'floor2-bathroom-mirror'
]) {
  const mirror = planItem(id);
  assert.equal(mirror.elementKind, 'mirror');
  assert(mirror.elevation >= 1, `${id} must mount above the basin`);
}
const server = http.createServer((req, res) => {
  const name = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
  const file = path.resolve(root, '.' + (name === '/' ? '/index.html' : name));
  if (!file.startsWith(root + path.sep)) return res.writeHead(403).end();
  fs.readFile(file, (error, data) => {
    if (error) return res.writeHead(404).end();
    res.setHeader('Content-Type', file.endsWith('.html') ? 'text/html' : file.endsWith('.json') ? 'application/json' : 'application/octet-stream');
    res.end(data);
  });
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({headless:true, channel:'chrome'});
    const page = await browser.newPage({viewport:{width:1920,height:1080}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(value => localStorage.setItem('home-floor-planner-v1', JSON.stringify(value)), plan);
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.waitForFunction(() => typeof three !== 'undefined' && three.isReady);
    await page.evaluate(value => applyPlanSnapshot(value), plan);
    const checks = [];
    for (const floor of plan.floors) {
      const key = floor.id.split('-').at(-1);
      await page.evaluate(floorId => {
        state.activeFloorId = floorId; state.viewFloor = floorId;
        els.viewFloorSelect.value=floorId;
        const rect=canvas.getBoundingClientRect();
        state.scale=Math.min((rect.width-80)/22,(rect.height-100)/15);
        centerPlan();
        const elevation=state.floors.find(f=>f.id===floorId).elevation;
        three.orbit.position.set(5,elevation+12,12);
        three.orbit.yaw = Math.PI; three.orbit.pitch = -.96;
        renderAll();
      }, floor.id);
      await page.waitForTimeout(200);
      checks.push(await page.evaluate(() => {
        updateCamera();
        const gl = three.renderer.getContext();
        const pixels = new Uint8Array(gl.drawingBufferWidth*gl.drawingBufferHeight*4);
        gl.readPixels(0,0,gl.drawingBufferWidth,gl.drawingBufferHeight,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
        const colors = new Set();
        for (let i=0;i<pixels.length;i+=64) colors.add(`${pixels[i]},${pixels[i+1]},${pixels[i+2]}`);
        const surfaces=[];
        three.root.traverse(mesh => {
          if (!mesh.userData.storySurface) return;
          const box = new THREE.Box3().setFromObject(mesh);
          const material = Array.isArray(mesh.material) ? mesh.material[0] : mesh.material;
          surfaces.push({role:mesh.userData.storySurface, floorId:mesh.userData.floorId,
            min:box.min.toArray(),max:box.max.toArray(),white:material.color?.getHex()===0xffffff});
        });
        return {floor:state.viewFloor,colors:colors.size,surfaces};
      }));
      assert.equal(checks.at(-1).floor,floor.id,'The requested floor must actually be rendered');
      await page.screenshot({path:path.join(output, `browser-${key}.png`)});
      await page.evaluate(() => {
        // Inspect interiors without changing the saved floor visibility settings.
        three.root.traverse(mesh => { if (mesh.userData.storySurface === 'ceiling' || mesh.userData.roofId) mesh.visible = false; });
        updateCamera();
      });
      await page.screenshot({path:path.join(output, `browser-${key}-cutaway.png`)});
    }
    for(const key of ['living','floor2']){
      await page.evaluate(key=>{
        const floor=state.floors.find(f=>f.id.endsWith('-'+key));
        state.activeFloorId=floor.id;state.viewFloor=floor.id;els.viewFloorSelect.value=floor.id;
        state.scale=110;
        const rect=canvas.getBoundingClientRect();
        state.offset={x:rect.width/2-5*state.scale,y:rect.height/2-2.2*state.scale};
        three.orbit.position.set(5,floor.elevation+6,6);
        three.orbit.yaw=Math.PI;three.orbit.pitch=-1;
        renderAll();
        three.root.traverse(mesh=>{if(mesh.userData.storySurface==='ceiling'||mesh.userData.roofId)mesh.visible=false;});
        updateCamera();
      },key);
      await page.screenshot({path:path.join(output,`browser-${key}-vertical-core.png`)});
    }
    await page.evaluate(() => {
      state.activeFloorId='architect-alt-4-v2-living';
      state.viewFloor=state.activeFloorId;
      els.viewFloorSelect.value=state.viewFloor;
      state.scale=85;
      const rect=canvas.getBoundingClientRect();
      state.offset={x:rect.width/2-10*state.scale,y:rect.height/2-7*state.scale};
      three.orbit.position.set(10,8,10);
      three.orbit.yaw=Math.PI;
      three.orbit.pitch=-1;
      renderAll();
      three.root.traverse(mesh => {if(mesh.userData.storySurface==='ceiling' || mesh.userData.roofId)mesh.visible=false;});
      updateCamera();
    });
    await page.screenshot({path:path.join(output,'browser-master-shower.png')});
    await page.evaluate(() => {
      state.activeFloorId='architect-alt-4-v2-living';
      state.viewFloor=state.activeFloorId;
      els.viewFloorSelect.value=state.viewFloor;
      state.scale=100;
      const rect=canvas.getBoundingClientRect();
      state.offset={x:rect.width/2-14.5*state.scale,y:rect.height/2-5.2*state.scale};
      three.orbit.position.set(17,4.9,5.2);
      three.orbit.yaw=-Math.PI/2;
      three.orbit.pitch=-.12;
      renderAll();
    });
    await page.screenshot({path:path.join(output,'browser-master-balcony.png')});
    await page.evaluate(() => {
      state.activeFloorId='architect-alt-4-v2-living';
      state.viewFloor=state.activeFloorId;
      els.viewFloorSelect.value=state.viewFloor;
      state.scale=110;
      const rect=canvas.getBoundingClientRect();
      state.offset={x:rect.width/2-9.2*state.scale,y:rect.height/2-2.3*state.scale};
      three.orbit.position.set(9.2,9,2.3);
      three.orbit.yaw=0;
      three.orbit.pitch=-1.45;
      renderAll();
      three.root.traverse(mesh => {if(mesh.userData.storySurface==='ceiling' || mesh.userData.roofId)mesh.visible=false;});
      updateCamera();
    });
    await page.screenshot({path:path.join(output,'browser-master-closet.png')});
    await page.evaluate(() => {
      state.viewFloor='all'; state.activeFloorId='architect-alt-4-v2-ground';
      three.orbit.position.set(8,1.6,6);three.orbit.yaw=3.5;three.orbit.pitch=.12;
      render3D();
    });
    await page.screenshot({path:path.join(output,'browser-all-interior.png')});
    await page.evaluate(() => {
      state.viewFloor='all';
      three.orbit.position.set(20,1.5,22);
      three.orbit.yaw=3.92;
      render3D();
      setCameraHorizon();
    });
    await page.screenshot({path:path.join(output,'browser-horizon-1p5.png')});
    await page.evaluate(() => { three.orbit.position.y=0; setCameraHorizon(); });
    await page.screenshot({path:path.join(output,'browser-horizon-0.png')});
    const isolation = await page.evaluate(() => {
      const surfaces=[];three.root.traverse(mesh=>{if(mesh.userData.storySurface) surfaces.push(mesh);});
      const ray = new THREE.Raycaster();
      const checks=[];
      for (const floor of state.floors) for (const slab of state.rooms.filter(r=>r.floorId===floor.id)) {
        for (const role of ['floor','ceiling']) for (const hole of slab[role+'Holes'] || []) {
          const targetY = role==='floor' ? floor.elevation+.04 : storyCeilingElevation(floor)-.03;
          ray.set(new THREE.Vector3(hole.x+hole.w/2,targetY+.15,hole.y+hole.h/2),new THREE.Vector3(0,-1,0));
          ray.far=.3;
          checks.push({role,floor:floor.id,blocked:ray.intersectObjects(surfaces.filter(m=>m.userData.floorId===floor.id && m.userData.storySurface===role)).length});
        }
      }
      return checks;
    });
    assert(isolation.length > 0);
    for (const check of isolation) assert.equal(check.blocked,0,JSON.stringify(check));
    const structuralOpenings=await page.evaluate(() => {
      const meshes=[];
      three.root.traverse(mesh=>{if(mesh.userData.storySurface) meshes.push(mesh);});
      const ray=new THREE.Raycaster();
      const blocked=(floorId,role,x,z,height)=>{
        ray.set(new THREE.Vector3(x,height+.15,z),new THREE.Vector3(0,-1,0));
        ray.far=.3;
        return ray.intersectObjects(meshes.filter(mesh=>mesh.userData.floorId===floorId && mesh.userData.storySurface===role)).length>0;
      };
      const stairChecks=[];
      for(const stair of state.stairs){
        const index=state.floors.findIndex(f=>f.id===stair.floorId);
        if(index<0 || index+1>=state.floors.length)continue;
        const source=state.floors[index],destination=state.floors[index+1];
        for(const piece of stairFootprintPieces(stair))for(let xi=1;xi<=5;xi++)for(let zi=1;zi<=5;zi++){
          const x=piece.x+piece.w*xi/6,z=piece.y+piece.h*zi/6;
          const polygon=piece.polygon;
          if(polygon && !polygon.every((a,i)=>{
            const b=polygon[(i+1)%polygon.length];
            return (b.x-a.x)*(z-a.y)-(b.y-a.y)*(x-a.x)>=-1e-8;
          }))continue;
          const inside=state.rooms.some(room=>room.floorId===destination.id && room.structuralSlab && x>room.x && x<room.x+room.w && z>room.y && z<room.y+room.h);
          if(!inside)continue;
          stairChecks.push({stair:stair.id,x,z,
            blockedFloor:blocked(destination.id,'floor',x,z,destination.elevation+.04),
            blockedCeiling:blocked(source.id,'ceiling',x,z,storyCeilingElevation(source)-.03)});
        }
      }
      const voidChecks=[];
      const hole=state.rooms.find(room=>room.floorId.endsWith('-living') && room.floorHoles?.some(entry=>entry.sourceHandle==='164D'))?.floorHoles[0];
      if(hole)for(let xi=1;xi<=9;xi++)for(let zi=1;zi<=9;zi++){
        const x=hole.x+hole.w*xi/10,z=hole.y+hole.h*zi/10;
        voidChecks.push({x,z,
          blockedLivingFloor:blocked('architect-alt-4-v2-living','floor',x,z,state.floors.find(f=>f.id.endsWith('-living')).elevation+.04),
          blockedGroundCeiling:blocked('architect-alt-4-v2-ground','ceiling',x,z,storyCeilingElevation(state.floors.find(f=>f.id.endsWith('-ground')))-.03)});
      }
      const shaftChecks=[];
      for(const floor of state.floors){
        for(const role of ['floor','ceiling']){
          if(role==='floor' && floor.id.endsWith('-basement') || role==='ceiling' && floor.id.endsWith('-floor2'))continue;
          const height=role==='floor'?floor.elevation+.04:storyCeilingElevation(floor)-.03;
          for(let xi=1;xi<=3;xi++)for(let zi=1;zi<=3;zi++){
            shaftChecks.push({floor:floor.id,role,blocked:blocked(floor.id,role,5.9106+xi/4,1.6831+1.5*zi/4,height)});
          }
        }
      }
      const basement=state.floors.find(f=>f.id.endsWith('-basement'));
      const top=state.floors.find(f=>f.id.endsWith('-floor2'));
      return {stairChecks,voidChecks,shaftChecks,
        shaftBaseSolid:blocked(basement.id,'floor',6.4106,2.4331,basement.elevation+.04),
        cancelledStairFloorSolid:blocked(top.id,'floor',5.25,2.5,top.elevation+.04)};
    });
    assert(structuralOpenings.stairChecks.length>100);
    assert(structuralOpenings.voidChecks.length===81);
    for(const check of structuralOpenings.stairChecks)assert(!check.blockedFloor && !check.blockedCeiling,JSON.stringify(check));
    for(const check of structuralOpenings.voidChecks)assert(!check.blockedLivingFloor && !check.blockedGroundCeiling,JSON.stringify(check));
    assert.equal(structuralOpenings.shaftChecks.length,54);
    for(const check of structuralOpenings.shaftChecks)assert(!check.blocked,JSON.stringify(check));
    assert(structuralOpenings.shaftBaseSolid,'Retain the basement floor under the future elevator');
    assert(structuralOpenings.cancelledStairFloorSolid,'The red-X upper stair projection must not remove the top floor');
    console.log('Structural openings:',structuralOpenings.stairChecks.length,'stair points and',structuralOpenings.voidChecks.length,'void points clear');
    const rotatedOpening=await page.evaluate(() => {
      const stair=state.stairs.find(item=>item.floorId.endsWith('-living'));
      const oldRotation=stair.rotation;
      stair.rotation=(oldRotation+90)%360;
      render3D();
      const floor=state.floors.find(item=>item.id.endsWith('-floor2'));
      const slabMeshes=[];
      three.root.traverse(mesh=>{if(mesh.userData.storySurface==='floor' && mesh.userData.floorId===floor.id)slabMeshes.push(mesh);});
      const ceilingMeshes=[];
      three.root.traverse(mesh=>{if(mesh.userData.storySurface==='ceiling' && mesh.userData.floorId===stair.floorId)ceilingMeshes.push(mesh);});
      const ray=new THREE.Raycaster();
      let checked=0,blocked=0,blockedCeiling=0;
      for(const piece of stairFootprintPieces(stair))for(let xi=1;xi<=5;xi++)for(let zi=1;zi<=5;zi++){
        const x=piece.x+piece.w*xi/6,z=piece.y+piece.h*zi/6;
        if(piece.polygon && !piece.polygon.every((a,i)=>{
          const b=piece.polygon[(i+1)%piece.polygon.length];
          return (b.x-a.x)*(z-a.y)-(b.y-a.y)*(x-a.x)>=-1e-8;
        }))continue;
        if(!state.rooms.some(room=>room.floorId===floor.id && room.structuralSlab && x>room.x && x<room.x+room.w && z>room.y && z<room.y+room.h))continue;
        checked++;
        ray.set(new THREE.Vector3(x,floor.elevation+.2,z),new THREE.Vector3(0,-1,0));
        ray.far=.4;
        if(ray.intersectObjects(slabMeshes).length)blocked++;
        if(ray.intersectObjects(ceilingMeshes).length)blockedCeiling++;
      }
      stair.rotation=oldRotation;
      render3D();
      return {checked,blocked,blockedCeiling};
    });
    assert(rotatedOpening.checked>10,JSON.stringify(rotatedOpening));
    assert.equal(rotatedOpening.blocked,0,JSON.stringify(rotatedOpening));
    assert.equal(rotatedOpening.blockedCeiling,0,JSON.stringify(rotatedOpening));
    await page.evaluate(() => {
      state.viewFloor='architect-alt-4-v2-ground';
      three.orbit.position.set(10.3,1.6,5.8);
      three.orbit.yaw=0;
      three.orbit.pitch=-.3;
      render3D();
    });
    await page.screenshot({path:path.join(output,'browser-kitchen-sink.png')});
    const sinkClearance=await page.evaluate(() => {
      const sink=state.elements.find(item=>item.name==='Kitchen sink 1');
      const group=three.root.children.find(item=>item.isGroup &&
        Math.abs(item.position.x-(sink.x+sink.w/2))<1e-6 &&
        Math.abs(item.position.z-(sink.y+sink.h/2))<1e-6);
      return group ? new THREE.Box3().setFromObject(group).max.y-sink.height : null;
    });
    assert(sinkClearance>.3,`Kitchen faucet clearance: ${sinkClearance}`);
    const guestSinkTop=await page.evaluate(() => {
      const sink=state.elements.find(item=>item.id.endsWith('ground-assembly-guest-toilet-sink'));
      const group=three.root.children.find(item=>item.isGroup &&
        Math.abs(item.position.x-(sink.x+sink.w/2))<1e-6 &&
        Math.abs(item.position.z-(sink.y+sink.h/2))<1e-6);
      return group ? new THREE.Box3().setFromObject(group).max.y : null;
    });
    assert(guestSinkTop>.8 && guestSinkTop<1.05,`Guest sink top: ${guestSinkTop}`);
    await page.evaluate(() => {
      state.viewFloor='all';
      els.viewFloorSelect.value='all';
      three.orbit.position.set(-.5,1.6,7.5);
      three.orbit.yaw=-1.85;
      three.orbit.pitch=-.26;
      render3D();
    });
    await page.screenshot({path:path.join(output,'browser-living-room-glazing.png')});
    for (const check of checks) {
      assert(check.colors>20, JSON.stringify(check));
      assert(check.surfaces.some(s=>s.role==='floor'));
      assert(check.surfaces.filter(s=>s.role==='ceiling').every(s=>s.white && s.floorId===check.floor));
    }
    const groundCeilings=checks.find(check=>check.floor.endsWith('-ground')).surfaces.filter(s=>s.role==='ceiling');
    assert(groundCeilings.length>0);
    for(const surface of groundCeilings){
      assert(Math.abs(surface.min[1]-2.79)<.001,JSON.stringify(surface));
      assert(Math.abs(surface.max[1]-3.14)<.001,JSON.stringify(surface));
    }
    const topSurface=await page.evaluate(() => {
      const floor=state.floors.find(item=>item.id.endsWith('-floor2'));
      state.viewFloor=floor.id;
      els.viewFloorSelect.value=floor.id;
      render3D();
      const roofs=[],ceilings=[],floors=[];
      three.root.traverse(mesh=>{
        if(mesh.userData.roofId)roofs.push(mesh);
        if(mesh.userData.storySurface==='ceiling' && mesh.userData.floorId===floor.id)ceilings.push(mesh);
        if(mesh.userData.storySurface==='floor' && mesh.userData.floorId===floor.id)floors.push(mesh);
      });
      const terrace=state.rooms.find(room=>room.name==='Roof terrace 3');
      const point={x:terrace.x+terrace.w/2,z:terrace.y+terrace.h/2};
      const ray=new THREE.Raycaster(new THREE.Vector3(point.x,12,point.z),new THREE.Vector3(0,-1,0));
      const terraceRoofHits=ray.intersectObjects(roofs).length;
      const terraceFloorHit=ray.intersectObjects(floors)[0];
      const roof=state.roofs.find(item=>item.floorId===floor.id);
      three.camera.position.set(13,11.5,13);
      three.camera.lookAt(3,7.2,4.5);
      three.camera.updateMatrixWorld();
      three.renderer.render(three.scene,three.camera);
      return {roofMeshes:roofs.length,undersides:roofs.filter(mesh=>mesh.userData.roofUnderside).length,
        ceilings:ceilings.length,terraceRoofHits,terraceColor:terraceFloorHit?.object.material.color.getHex(),
        roofBounds:new THREE.Box3().setFromObject(roofs.find(mesh=>!mesh.userData.roofUnderside)).min.toArray(),
        roofX:roof.x,roofWest:roof.x+roof.w};
    });
    assert.equal(topSurface.roofMeshes,2,JSON.stringify(topSurface));
    assert.equal(topSurface.undersides,1,JSON.stringify(topSurface));
    assert.equal(topSurface.ceilings,0,JSON.stringify(topSurface));
    assert.equal(topSurface.terraceRoofHits,0,JSON.stringify(topSurface));
    assert.equal(topSurface.terraceColor,0xd9dee5,JSON.stringify(topSurface));
    await page.screenshot({path:path.join(output,'browser-roof-terrace.png')});
    const beforeMove=await page.evaluate(()=>three.orbit.position.toArray());
    await page.locator('#threeCanvas').hover();
    await page.keyboard.down('w');
    await page.waitForTimeout(180);
    await page.keyboard.up('w');
    const afterMove=await page.evaluate(()=>three.orbit.position.toArray());
    assert(Math.hypot(...afterMove.map((v,i)=>v-beforeMove[i]))>.02,'Keyboard movement must change the camera');
    const walkDirections=await page.evaluate(() => {
      const checks=[];
      for(const [yaw,pitch] of [[0,0],[Math.PI/2,.8],[2.4,-.95]]){
        three.orbit.position.set(4,1.6,6);
        three.orbit.yaw=yaw;
        three.orbit.pitch=pitch;
        updateCamera();
        const expected=new THREE.Vector3();
        three.camera.getWorldDirection(expected);
        expected.y=0;
        expected.normalize();
        const start=three.orbit.position.clone();
        moveCameraByKey('w');
        const forward=three.orbit.position.clone().sub(start);
        moveCameraByKey('s');
        const returned=three.orbit.position.clone().sub(start);
        checks.push({expected:expected.toArray(),forward:forward.toArray(),returned:returned.toArray()});
      }
      return checks;
    });
    for(const check of walkDirections){
      assert(Math.abs(check.forward[1])<1e-8,JSON.stringify(check));
      assert(Math.abs(check.forward[0]-check.expected[0]*.1)<1e-6,JSON.stringify(check));
      assert(Math.abs(check.forward[2]-check.expected[2]*.1)<1e-6,JSON.stringify(check));
      assert(check.returned.every(value=>Math.abs(value)<1e-6),JSON.stringify(check));
    }
    const wheelDirections=await page.evaluate(() => {
      three.orbit.position.set(4,1.5,6);
      three.orbit.yaw=1.1;
      three.orbit.pitch=.7;
      three.wheelSteps=[];
      updateCamera();
      const heading=cameraWalkVector();
      const yaw=three.orbit.yaw;
      const start=three.orbit.position.clone();
      moveCameraByWheel({deltaX:0,deltaY:-120,deltaMode:0,shiftKey:false});
      const forward=three.orbit.position.clone().sub(start);
      moveCameraByWheel({deltaX:0,deltaY:120,deltaMode:0,shiftKey:false});
      const returned=three.orbit.position.clone().sub(start);
      moveCameraByWheel({deltaX:-120,deltaY:0,deltaMode:0,shiftKey:false});
      const raised=three.orbit.position.clone().sub(start);
      moveCameraByWheel({deltaX:120,deltaY:0,deltaMode:0,shiftKey:false});
      const lowered=three.orbit.position.clone().sub(start);
      moveCameraByWheel({deltaX:0,deltaY:-120,deltaMode:0,shiftKey:true});
      const shiftRaised=three.orbit.position.clone().sub(start);
      moveCameraByWheel({deltaX:-120,deltaY:0,deltaMode:0,shiftKey:false});
      const repeatedRaise=three.orbit.position.clone().sub(start);
      moveCameraByKey('z');
      const keyLowered=three.orbit.position.clone().sub(start);
      moveCameraByKey('c');
      const keyRaised=three.orbit.position.clone().sub(start);
      three.orbit.position.y=0;
      moveCameraByWheel({deltaX:120,deltaY:0,deltaMode:0,shiftKey:false});
      return {heading:heading.toArray(),forward:forward.toArray(),returned:returned.toArray(),
        raised:raised.toArray(),lowered:lowered.toArray(),shiftRaised:shiftRaised.toArray(),
        repeatedRaise:repeatedRaise.toArray(),keyLowered:keyLowered.toArray(),keyRaised:keyRaised.toArray(),
        groundHeight:three.orbit.position.y,yawBefore:yaw,yawAfter:three.orbit.yaw};
    });
    assert(Math.abs(wheelDirections.forward[1])<1e-8,JSON.stringify(wheelDirections));
    assert(Math.abs(wheelDirections.forward[0]-wheelDirections.heading[0]*.1)<1e-6,JSON.stringify(wheelDirections));
    assert(Math.abs(wheelDirections.forward[2]-wheelDirections.heading[2]*.1)<1e-6,JSON.stringify(wheelDirections));
    assert(wheelDirections.returned.every(value=>Math.abs(value)<1e-6),JSON.stringify(wheelDirections));
    assert(Math.abs(wheelDirections.raised[1]-.2)<1e-6,JSON.stringify(wheelDirections));
    assert(wheelDirections.lowered.every(value=>Math.abs(value)<1e-6),JSON.stringify(wheelDirections));
    assert(Math.abs(wheelDirections.shiftRaised[1]-.2)<1e-6,JSON.stringify(wheelDirections));
    assert(Math.abs(wheelDirections.repeatedRaise[1]-.4)<1e-6,JSON.stringify(wheelDirections));
    assert(Math.abs(wheelDirections.keyLowered[1]-.2)<1e-6,JSON.stringify(wheelDirections));
    assert(Math.abs(wheelDirections.keyRaised[1]-.4)<1e-6,JSON.stringify(wheelDirections));
    assert.equal(wheelDirections.groundHeight,0);
    assert.equal(wheelDirections.yawAfter,wheelDirections.yawBefore);
    const acceleratedWheel=await page.evaluate(() => {
      three.orbit.position.set(4,1.5,6);
      three.wheelSteps=[];
      updateCamera();
      const heading=cameraWalkVector();
      const start=three.orbit.position.clone();
      const distances=[];
      for(let i=0;i<3;i++){
        moveCameraByWheel({deltaX:0,deltaY:-120,deltaMode:0,shiftKey:false});
        distances.push(three.orbit.position.clone().sub(start).dot(heading));
      }
      return {distances,height:three.orbit.position.y};
    });
    for(const [index,expected] of [.1,.2,1.2].entries()){
      assert(Math.abs(acceleratedWheel.distances[index]-expected)<1e-6,JSON.stringify(acceleratedWheel));
    }
    assert.equal(acceleratedWheel.height,1.5);
    await page.evaluate(() => { three.orbit.position.y=1.5; three.orbit.pitch=.3; updateCamera(); });
    await page.locator('#horizonCameraBtn').click();
    const horizon=await page.evaluate(() => {
      const ray=new THREE.Raycaster();
      ray.setFromCamera(new THREE.Vector2(0,0),three.camera);
      const pitch=three.orbit.pitch;
      const centerRayY=ray.ray.direction.y;
      const initialHeight=three.orbit.position.y;
      moveCameraByKey('w');
      const keyHeight=three.orbit.position.y;
      moveCameraByWheel({deltaX:0,deltaY:-120,deltaMode:0,shiftKey:false});
      const wheelHeight=three.orbit.position.y;
      three.orbit.position.y=0;
      setCameraHorizon();
      const groundHeight=three.orbit.position.y;
      moveCameraByKey('w');
      return {pitch,centerRayY,initialHeight,keyHeight,wheelHeight,groundHeight,
        movedGroundHeight:three.orbit.position.y};
    });
    assert(Math.abs(horizon.pitch+Math.PI/12)<.0001,JSON.stringify(horizon));
    assert(horizon.centerRayY<-.25,JSON.stringify(horizon));
    assert.equal(horizon.initialHeight,1.5);
    assert.equal(horizon.keyHeight,1.5);
    assert.equal(horizon.wheelHeight,1.5);
    assert.equal(horizon.groundHeight,0);
    assert.equal(horizon.movedGroundHeight,0);
    const fullscreenButton=page.locator('#fullscreen3DBtn');
    await fullscreenButton.click();
    await page.waitForFunction(() => document.getElementById('fullscreen3DBtn').getAttribute('aria-pressed')==='true');
    await page.waitForFunction(() => three.renderer.domElement.width>=document.getElementById('threeCanvas').getBoundingClientRect().width);
    const fullscreen=await page.evaluate(() => {
      const view=document.getElementById('viewShell').getBoundingClientRect();
      const canvas=document.getElementById('threeCanvas').getBoundingClientRect();
      return {view:{x:view.x,y:view.y,width:view.width,height:view.height},
        canvas:{width:canvas.width,height:canvas.height},
        buffer:{width:three.renderer.domElement.width,height:three.renderer.domElement.height},
        viewport:{width:innerWidth,height:innerHeight}};
    });
    assert(Math.abs(fullscreen.view.x)<2 && Math.abs(fullscreen.view.y)<2,JSON.stringify(fullscreen));
    assert(Math.abs(fullscreen.view.width-fullscreen.viewport.width)<2,JSON.stringify(fullscreen));
    assert(Math.abs(fullscreen.view.height-fullscreen.viewport.height)<2,JSON.stringify(fullscreen));
    assert(fullscreen.canvas.width>fullscreen.viewport.width*.8,JSON.stringify(fullscreen));
    assert(fullscreen.buffer.width>=fullscreen.canvas.width,JSON.stringify(fullscreen));
    await page.screenshot({path:path.join(output,'browser-fullscreen.png')});
    await fullscreenButton.click();
    await page.waitForFunction(() => document.getElementById('fullscreen3DBtn').getAttribute('aria-pressed')==='false');
    await fullscreenButton.click();
    await page.waitForFunction(() => document.getElementById('fullscreen3DBtn').getAttribute('aria-pressed')==='true');
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => document.getElementById('fullscreen3DBtn').getAttribute('aria-pressed')==='false');
    await page.setViewportSize({width:390,height:844});
    await page.waitForTimeout(150);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),'Mobile page must not overflow horizontally');
    await page.evaluate(()=>{
      state.viewFloor='architect-alt-4-v2-ground';els.viewFloorSelect.value=state.viewFloor;
      three.orbit.position.set(5,12,12);three.orbit.yaw=Math.PI;three.orbit.pitch=-.96;
      renderAll();
    });
    await page.locator('.view-shell').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(output,'browser-mobile-view.png')});
    await page.evaluate(() => { document.getElementById('viewShell').requestFullscreen=undefined; });
    await fullscreenButton.click();
    await page.waitForFunction(() => document.getElementById('fullscreen3DBtn').getAttribute('aria-pressed')==='true');
    const mobileFullscreen=await page.evaluate(() => {
      const view=document.getElementById('viewShell').getBoundingClientRect();
      const canvas=document.getElementById('threeCanvas').getBoundingClientRect();
      return {view:{x:view.x,y:view.y,width:view.width,height:view.height},canvasHeight:canvas.height,
        viewport:{width:innerWidth,height:innerHeight}};
    });
    assert(Math.abs(mobileFullscreen.view.x)<2 && Math.abs(mobileFullscreen.view.y)<2,JSON.stringify(mobileFullscreen));
    assert(Math.abs(mobileFullscreen.view.width-mobileFullscreen.viewport.width)<2,JSON.stringify(mobileFullscreen));
    assert(Math.abs(mobileFullscreen.view.height-mobileFullscreen.viewport.height)<2,JSON.stringify(mobileFullscreen));
    assert(mobileFullscreen.canvasHeight>mobileFullscreen.viewport.height*.5,JSON.stringify(mobileFullscreen));
    await page.screenshot({path:path.join(output,'browser-mobile-fullscreen.png')});
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => document.getElementById('fullscreen3DBtn').getAttribute('aria-pressed')==='false');
    await page.screenshot({path:path.join(output,'browser-mobile.png'),fullPage:true});
    assert.equal(errors.length,0,errors.join('\n'));
    fs.writeFileSync(path.join(output,'browser-checks.json'),JSON.stringify({checks,isolation,errors},null,2));
    console.log(JSON.stringify({floors:checks.map(c=>({floor:c.floor,colors:c.colors,surfaces:c.surfaces.length})),voidRayChecks:isolation.length,errors}));
  } finally {
    if (browser) await browser.close();
    server.close();
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
