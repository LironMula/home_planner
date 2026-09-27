const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const server = http.createServer((req, res) => {
  const name = new URL(req.url, 'http://localhost').pathname;
  if (name === '/favicon.ico') return res.writeHead(204).end();
  const file = path.resolve(root, '.' + (name === '/' ? '/index.html' : name));
  if (!file.startsWith(root + path.sep)) return res.writeHead(403).end();
  fs.readFile(file, (error, data) => {
    if (error) return res.writeHead(404).end();
    res.setHeader('Content-Type', file.endsWith('.html') ? 'text/html' : 'application/json');
    res.end(data);
  });
});

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({ headless: true, channel: 'chrome' });
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.waitForFunction(() => typeof three !== 'undefined' && three.isReady);
    assert.equal(await page.evaluate(() => state.cameraMode), '35mm', 'Fresh default');
    const plan = JSON.parse(fs.readFileSync(path.join(root, 'plans/architect-alt-4-v2.json'), 'utf8'));
    for (const [savedMode, expected] of [[null, '35mm'], ['human', '35mm'], ['invalid', '35mm'],
      ['24mm', '24mm'], ['35mm', '35mm'], ['fixed', 'fixed']]) {
      const loaded = await page.evaluate(({ plan, savedMode }) => {
        applyPlanSnapshot({ ...plan, cameraMode: savedMode });
        return { mode: state.cameraMode, saved: planSnapshot().cameraMode, focal: three.camera.getFocalLength() };
      }, { plan, savedMode });
      assert.equal(loaded.mode, expected);
      assert.equal(loaded.saved, expected);
      if (expected !== 'fixed') assert(Math.abs(loaded.focal - parseInt(expected)) < 1e-8);
    }
    const output = path.join(root, 'pdf_renders/camera-lenses');
    fs.mkdirSync(output, { recursive: true });
    for (const layout of ['split', 'fullscreen', 'mobile']) {
      if (layout === 'fullscreen') {
        await page.evaluate(() => { els.viewShell.requestFullscreen = undefined; });
        await page.locator('#fullscreen3DBtn').click();
      }
      if (layout === 'mobile') await page.setViewportSize({ width: 390, height: 844 });
      await page.waitForTimeout(200);
      const fovs = [];
      for (const lens of [35, 24]) {
        await page.locator('#cameraModeBtn').click();
        await page.locator(`[data-camera-mode="${lens}mm"]`).click();
        assert.equal(await page.locator(`[data-camera-mode="${lens}mm"]`).getAttribute('aria-checked'), 'true');
        const checks = await page.evaluate(lens => {
          const originalScene = three.scene, originalMirrors = three.mirrors;
          const aspect = three.camera.aspect;
          const halfHeight = 10 * (36 / Math.max(aspect, 1)) / (2 * lens);
          const expectedFov = 2 * Math.atan(halfHeight / 10) * 180 / Math.PI;
          const results = [];
          try {
            three.scene = new THREE.Scene();
            three.scene.background = new THREE.Color(0);
            three.mirrors = [];
            // Collinear world points must stay collinear, including near screen edges.
            const points = [-.8, 0, .8].flatMap(y => [-.8, -.4, 0, .4, .8].map(x => [x, y]));
            for (const [yaw, pitch] of [[Math.PI, 0], [0.7, -.3]]) {
              three.orbit.position.set(3, 1.5, 4);
              three.orbit.yaw = yaw; three.orbit.pitch = pitch;
              updateCamera();
              const markers = points.map(([x, y]) => {
                const marker = new THREE.Mesh(new THREE.SphereGeometry(.055, 12, 8),
                  new THREE.MeshBasicMaterial({ color: 0xff0000 }));
                marker.position.set(x * halfHeight * aspect, y * halfHeight, -10)
                  .applyQuaternion(three.camera.quaternion).add(three.camera.position);
                three.scene.add(marker);
                return marker;
              });
              updateCamera();
              const gl = three.renderer.getContext();
              for (const [x, y] of points) {
                const pixel = new Uint8Array(4);
                gl.readPixels(Math.floor((x + 1) / 2 * gl.drawingBufferWidth),
                  Math.floor((y + 1) / 2 * gl.drawingBufferHeight), 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
                results.push({ x, y, yaw, pitch, pixel: [...pixel] });
              }
              for (const marker of markers) {
                three.scene.remove(marker); marker.geometry.dispose(); marker.material.dispose();
              }
            }
          } finally {
            three.scene = originalScene; three.mirrors = originalMirrors;
          }
          return { results, expectedFov, actualFov: three.camera.fov, panorama: !!three.panorama };
        }, lens);
        assert.equal(checks.panorama, false);
        assert(Math.abs(checks.expectedFov - checks.actualFov) < 1e-8);
        fovs.push(checks.actualFov);
        for (const check of checks.results) assert(check.pixel[0] > 200 && check.pixel[1] < 20,
          JSON.stringify({ layout, lens, ...check }));
        const house = await page.evaluate(() => {
          state.viewFloor = 'all'; els.viewFloorSelect.value = 'all';
          three.orbit.position.set(-8, 1.5, 16);
          three.orbit.yaw = 2.4; three.orbit.pitch = -.1;
          render3D();
          const gl = three.renderer.getContext();
          const pixels = new Uint8Array(gl.drawingBufferWidth * gl.drawingBufferHeight * 4);
          gl.readPixels(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
          const colors = new Set();
          for (let i = 0; i < pixels.length; i += 64) colors.add(`${pixels[i]},${pixels[i + 1]},${pixels[i + 2]}`);
          const before = three.orbit.position.clone();
          moveCameraByKey('w', false, 10000);
          return { colors: colors.size, initialY: before.y, afterY: three.orbit.position.y,
            moved: before.distanceTo(three.orbit.position) };
        });
        assert(house.colors > 20, JSON.stringify(house));
        assert.equal(house.initialY, house.afterY);
        assert(house.moved > 0);
        await page.screenshot({ path: path.join(output, `${layout}-${lens}mm.png`) });
        console.log(JSON.stringify({ layout, lens, projectionChecks: checks.results.length, fov: checks.actualFov, house }));
      }
      assert(fovs[1] > fovs[0], '24 mm must be wider than 35 mm');
      const fixed = await page.evaluate(() => {
        setCameraMode('fixed');
        const rect = threeCanvas.getBoundingClientRect();
        const aspect = fixedCameraBaselineAspect(rect);
        return { actual: three.camera.fov, expected: 2 * Math.atan(Math.tan(50 * Math.PI / 180) / aspect) * 180 / Math.PI };
      });
      assert(Math.abs(fixed.actual - fixed.expected) < 1e-8);
    }
    const reflection = await page.evaluate(() => {
      setCameraMode('35mm');
      const mirror = three.mirrors[0];
      if (!mirror) return null;
      three.scene.updateMatrixWorld(true);
      const position = new THREE.Vector3().setFromMatrixPosition(mirror.surface.matrixWorld);
      const normal = new THREE.Vector3(0, 0, 1).transformDirection(mirror.surface.matrixWorld);
      three.orbit.position.copy(position).addScaledVector(normal, 1.4);
      const direction = normal.clone().negate();
      three.orbit.yaw = Math.atan2(direction.x, direction.z); three.orbit.pitch = 0;
      updateCamera();
      const pixels = new Uint8Array(mirror.renderTarget.width * mirror.renderTarget.height * 4);
      three.renderer.readRenderTargetPixels(mirror.renderTarget, 0, 0,
        mirror.renderTarget.width, mirror.renderTarget.height, pixels);
      const colors = new Set();
      for (let i = 0; i < pixels.length; i += 16) colors.add(`${pixels[i]},${pixels[i + 1]},${pixels[i + 2]}`);
      return { colors: colors.size, avatarHidden: !three.reflectionAvatar.visible,
        targetRestored: three.renderer.getRenderTarget() === null };
    });
    assert(reflection?.colors > 5, JSON.stringify(reflection));
    assert(reflection.avatarHidden && reflection.targetRestored);
    await page.screenshot({ path: path.join(output, 'mirror.png') });
    await page.evaluate(() => { setCameraMode('24mm'); savePlan(); });
    await page.reload();
    await page.waitForFunction(() => typeof three !== 'undefined' && three.isReady);
    assert.equal(await page.evaluate(() => state.cameraMode), '24mm');
    assert.deepEqual(errors, []);
    console.log('Lens projection, straight lines, persistence, migration, mirrors and navigation passed.');
  } finally {
    await browser?.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
