const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { createHash } = require('node:crypto');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const alternatives = process.argv.slice(2).map(Number);
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
    browser = await chromium.launch({headless: true, channel: 'chrome'});
    for (const alt of alternatives.length ? alternatives : [3, 5]) {
      assert([3, 5].includes(alt));
      const plan = JSON.parse(fs.readFileSync(path.join(root, `plans/architect-alt-${alt}-v2.json`), 'utf8'));
      const output = path.join(root, `pdf_renders/alt${alt}-v2`);
      fs.mkdirSync(output, {recursive: true});
      const page = await browser.newPage({viewport: {width: 1920, height: 1080}});
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.addInitScript(value => localStorage.setItem('home-floor-planner-v1', JSON.stringify(value)), plan);
      await page.goto(`http://127.0.0.1:${server.address().port}/`);
      await page.waitForFunction(() => typeof three !== 'undefined' && three.isReady);
      await page.evaluate(value => applyPlanSnapshot(value), plan);
      const entrance = await page.evaluate(ids => {
        updateCamera();
        const openings=state.openings.filter(o => ids.includes(o.id));
        const center=new THREE.Vector3(openings.reduce((s,o)=>s+o.x,0)/openings.length,
          three.orbit.position.y, openings.reduce((s,o)=>s+o.y,0)/openings.length);
        const direction=center.clone().sub(three.orbit.position).normalize();
        const facing=direction.dot(cameraForwardVector());
        const projected=center.clone().project(three.camera);
        // Aim into a leaf, not the sub-millimetre seam between paired leaves.
        const leafDirection=new THREE.Vector3(openings[0].x,center.y,openings[0].y)
          .sub(three.orbit.position).normalize();
        const ray=new THREE.Raycaster(three.orbit.position,leafDirection,0,4.1);
        ray.camera=three.camera;
        const hit=ray.intersectObjects(three.root.children,true).find(h => h.object.isMesh);
        let object=hit?.object, openingId;
        while(object) {
          openingId ||= three.doors.find(d => d.parent === object)?.opening.id;
          object=object.parent;
        }
        return {facing, projected:projected.toArray(), openingId, hit:hit && {distance:hit.distance,
          point:hit.point.toArray(), data:hit.object.userData}, position:three.orbit.position.toArray(),
          context:state.elements.filter(e=>e.context).length};
      }, plan.siteRegistration.entranceIds);
      await page.screenshot({path:path.join(output,'browser-default-entrance.png')});
      assert(entrance.facing > .9999 && Math.abs(entrance.projected[0]) < .001);
      assert(plan.siteRegistration.entranceIds.includes(entrance.openingId), JSON.stringify(entrance));
      assert(entrance.context >= 28);
      await page.screenshot({path:path.join(output,'browser-default-entrance.png')});
      const checks = [];
      for (const floor of plan.floors) {
        const key = floor.id.split('-').at(-1);
        await page.evaluate(floor => {
          state.activeFloorId = floor.id;
          state.viewFloor = floor.id;
          els.viewFloorSelect.value = floor.id;
          const rooms = state.rooms.filter(r => r.floorId === floor.id);
          const xmin = Math.min(...rooms.map(r => r.x)), xmax = Math.max(...rooms.map(r => r.x + r.w));
          const ymin = Math.min(...rooms.map(r => r.y)), ymax = Math.max(...rooms.map(r => r.y + r.h));
          const rect = canvas.getBoundingClientRect();
          state.scale = Math.min((rect.width - 80) / (xmax - xmin), (rect.height - 100) / (ymax - ymin));
          state.offset = {x: rect.width / 2 - (xmin + xmax) / 2 * state.scale, y: rect.height / 2 - (ymin + ymax) / 2 * state.scale};
          three.orbit.position.set((xmin + xmax) / 2, floor.elevation + 9, ymax + 2);
          three.orbit.yaw = Math.PI;
          three.orbit.pitch = -.9;
          renderAll();
        }, floor);
        await page.screenshot({path: path.join(output, `browser-${key}.png`)});
        const check = await page.evaluate(() => {
          const floor = state.floors.find(f => f.id === state.viewFloor);
          const surfaces = [];
          three.root.traverse(mesh => {
            if (mesh.userData.storySurface) surfaces.push(mesh);
            if (mesh.userData.storySurface === 'ceiling' || mesh.userData.roofId) mesh.visible = false;
          });
          updateCamera();
          const gl = three.renderer.getContext();
          const pixels = new Uint8Array(gl.drawingBufferWidth * gl.drawingBufferHeight * 4);
          gl.readPixels(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
          const colors = new Set();
          for (let i = 0; i < pixels.length; i += 64) colors.add(`${pixels[i]},${pixels[i+1]},${pixels[i+2]}`);
          const indoor = state.rooms.filter(r => r.floorId === floor.id && !r.outdoor && r.structuralSlab);
          const holes = [...indoor.flatMap(r => r.floorHoles || []),
            ...state.stairs.filter(s => s.floorId !== floor.id &&
              Math.abs(state.floors.find(f => f.id === s.floorId).elevation + s.height - floor.elevation) < .01).flatMap(stairFootprintPieces)];
          const meshes = surfaces.filter(m => m.userData.storySurface === 'floor');
          let holeChecks = 0;
          const blocked = [];
          for (const h of holes) {
            for (const u of [.2, .5, .8]) for (const v of [.2, .5, .8]) {
              const x = h.x + h.w * u, z = h.y + h.h * v;
              if (!indoor.some(r => x > r.x && x < r.x + r.w && z > r.y && z < r.y + r.h)) continue;
              const ray = new THREE.Raycaster(new THREE.Vector3(x, floor.elevation + .5, z), new THREE.Vector3(0, -1, 0), 0, .7);
              if (ray.intersectObjects(meshes).length) blocked.push({x, z});
              holeChecks++;
            }
          }
          return {floor: floor.id, colors: colors.size, surfaces: surfaces.length, holeChecks, blocked,
            textures: meshes.filter(m => m.material.map).length};
        });
        assert(check.colors > 20, JSON.stringify(check));
        assert.equal(check.blocked.length, 0, `Slab blocks a source opening: ${JSON.stringify(check)}`);
        if (['ground', 'living', 'top'].includes(key)) assert(check.textures > 0, `Missing floor finish: ${key}`);
        checks.push(check);
        await page.screenshot({path: path.join(output, `browser-${key}-cutaway.png`)});
        await page.evaluate(floor => {
          const rooms = state.rooms.filter(r => r.floorId === floor.id && !r.outdoor);
          const main = rooms.toSorted((a, b) => b.w * b.h - a.w * a.h)[0];
          three.orbit.position.set(main.x + main.w * .5, floor.elevation + 1.6, main.y + main.h * .75);
          three.orbit.yaw = Math.PI; three.orbit.pitch = -.06;
          render3D();
        }, floor);
        await page.screenshot({path: path.join(output, `browser-${key}-human.png`)});
      }
      if (alt === 5) {
        const glazing = await page.evaluate(() => {
          state.viewFloor = 'architect-alt-5-v2-ground';
          state.activeFloorId = state.viewFloor;
          els.viewFloorSelect.value = state.viewFloor;
          const rect = canvas.getBoundingClientRect();
          state.scale = 110;
          state.offset = {x:rect.width/2-7.7*state.scale,y:rect.height/2-6.7*state.scale};
          three.orbit.position.set(7.2, 1.6, 5.4);
          three.orbit.yaw = .45; three.orbit.pitch = -.08;
          renderAll();
          return state.openings.filter(o => o.id.includes('kitchen-') && o.id.includes('corner-window')).map(o => {
            const direction = o.name.includes('north') ? new THREE.Vector3(0,0,1) : new THREE.Vector3(1,0,0);
            const origin = new THREE.Vector3(o.x, 1.6, o.y).addScaledVector(direction,-.4);
            const ray = new THREE.Raycaster(origin,direction,0,.8);
            ray.camera = three.camera;
            const hit = ray.intersectObjects(three.root.children,true).find(h => h.object.isMesh);
            return {id:o.id, color:hit?.object.material.color?.getHexString()};
          });
        });
        assert.equal(glazing.length,2);
        for (const pane of glazing) assert.equal(pane.color,'45a9d8',JSON.stringify(pane));
        await page.screenshot({path:path.join(output,'browser-kitchen-corner.png')});
        const bathroom = await page.evaluate(() => {
          state.viewFloor = 'architect-alt-5-v2-living';
          state.activeFloorId = state.viewFloor;
          els.viewFloorSelect.value = state.viewFloor;
          const floor = state.floors.find(f => f.id === state.viewFloor);
          const rect = canvas.getBoundingClientRect();
          state.scale = 150;
          state.offset = {x:rect.width/2-9*state.scale,y:rect.height/2-7.2*state.scale};
          three.orbit.position.set(8.65,floor.elevation+1.6,7.6);
          three.orbit.yaw = Math.PI/2; three.orbit.pitch = -.12;
          renderAll();
          return [.9,1.6,2.4].map(height => {
            const ray = new THREE.Raycaster(new THREE.Vector3(9.6,floor.elevation+height,7.5),
              new THREE.Vector3(1,0,0),0,.6);
            ray.camera = three.camera;
            const hit = ray.intersectObjects(three.root.children,true).find(h => h.object.isMesh);
            return hit?.object.material.color?.getHexString();
          });
        });
        assert.deepEqual(bathroom,['fefdfa','45a9d8','fefdfa'],'Bathroom wall below/above glazing');
        await page.screenshot({path:path.join(output,'browser-master-toilet-wall.png')});
      }
      for (const [index, pose] of [[18, 9, 14, 3.95], [-3, 9, 14, 2.4], [18, 9, -5, -1.1], [-3, 9, -5, .85]].entries()) {
        await page.evaluate(pose => {
          state.viewFloor = 'all'; els.viewFloorSelect.value = 'all';
          three.orbit.position.set(pose[0], pose[1], pose[2]); three.orbit.yaw = pose[3]; three.orbit.pitch = -.25;
          renderAll();
        }, pose);
        await page.screenshot({path: path.join(output, `browser-exterior-${index}.png`)});
      }
      await page.setViewportSize({width: 390, height: 844});
      await page.evaluate(camera => {
        applyCameraSnapshot(camera); updateCamera();
      }, plan.camera);
      await page.locator('.view-shell').scrollIntoViewIfNeeded();
      await page.evaluate(() => { document.getElementById('viewShell').requestFullscreen = undefined; });
      await page.locator('#fullscreen3DBtn').click();
      await page.waitForFunction(() => document.getElementById('fullscreen3DBtn').getAttribute('aria-pressed') === 'true');
      assert(await page.evaluate(() => three.renderer.domElement.width > 300));
      await page.screenshot({path: path.join(output, 'browser-mobile.png')});
      assert.equal(errors.length, 0, errors.join('\n'));
      const planSha256 = createHash('sha256').update(fs.readFileSync(path.join(root, `plans/architect-alt-${alt}-v2.json`))).digest('hex');
      fs.writeFileSync(path.join(output, 'browser-checks.json'), JSON.stringify({planSha256, entrance, checks, errors}, null, 2));
      console.log(JSON.stringify({alternative: alt, checks, errors}));
      await page.close();
    }
  } finally {
    if (browser) await browser.close();
    server.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
