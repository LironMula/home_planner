const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'pdf_renders/alt4-v2');
const plan = JSON.parse(fs.readFileSync(path.join(root, 'plans/architect-alt-4-v2.json'), 'utf8'));
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
    for (const check of checks) {
      assert(check.colors>20, JSON.stringify(check));
      assert(check.surfaces.some(s=>s.role==='floor'));
      assert(check.surfaces.filter(s=>s.role==='ceiling').every(s=>s.white && s.floorId===check.floor));
    }
    const beforeMove=await page.evaluate(()=>three.orbit.position.toArray());
    await page.locator('#threeCanvas').hover();
    await page.keyboard.down('w');
    await page.waitForTimeout(180);
    await page.keyboard.up('w');
    const afterMove=await page.evaluate(()=>three.orbit.position.toArray());
    assert(Math.hypot(...afterMove.map((v,i)=>v-beforeMove[i]))>.02,'Keyboard movement must change the camera');
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
