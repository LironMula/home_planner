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
      for (const [index, pose] of [[18, 9, 14, 3.95], [-3, 9, 14, 2.4], [18, 9, -5, -1.1], [-3, 9, -5, .85]].entries()) {
        await page.evaluate(pose => {
          state.viewFloor = 'all'; els.viewFloorSelect.value = 'all';
          three.orbit.position.set(pose[0], pose[1], pose[2]); three.orbit.yaw = pose[3]; three.orbit.pitch = -.25;
          renderAll();
        }, pose);
        await page.screenshot({path: path.join(output, `browser-exterior-${index}.png`)});
      }
      await page.setViewportSize({width: 390, height: 844});
      await page.locator('.view-shell').scrollIntoViewIfNeeded();
      await page.evaluate(() => { document.getElementById('viewShell').requestFullscreen = undefined; });
      await page.locator('#fullscreen3DBtn').click();
      await page.waitForFunction(() => document.getElementById('fullscreen3DBtn').getAttribute('aria-pressed') === 'true');
      assert(await page.evaluate(() => three.renderer.domElement.width > 300));
      await page.screenshot({path: path.join(output, 'browser-mobile.png')});
      assert.equal(errors.length, 0, errors.join('\n'));
      const planSha256 = createHash('sha256').update(fs.readFileSync(path.join(root, `plans/architect-alt-${alt}-v2.json`))).digest('hex');
      fs.writeFileSync(path.join(output, 'browser-checks.json'), JSON.stringify({planSha256, checks, errors}, null, 2));
      console.log(JSON.stringify({alternative: alt, checks, errors}));
      await page.close();
    }
  } finally {
    if (browser) await browser.close();
    server.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
