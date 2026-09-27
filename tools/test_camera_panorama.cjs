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
    const plan = JSON.parse(fs.readFileSync(path.join(root, 'plans/architect-alt-4-v2.json'), 'utf8'));
    await page.addInitScript(value => localStorage.setItem('home-floor-planner-v1', JSON.stringify(value)), plan);
    await page.goto(`http://127.0.0.1:${server.address().port}/`);
    await page.waitForFunction(() => typeof three !== 'undefined' && three.isReady);
    await page.evaluate(value => applyPlanSnapshot(value), plan);
    const output = path.join(root, 'pdf_renders/camera-panorama');
    fs.mkdirSync(output, { recursive: true });
    for (const layout of ['split', 'fullscreen', 'mobile']) {
      if (layout === 'fullscreen') {
        await page.evaluate(() => { els.viewShell.requestFullscreen = undefined; });
        await page.locator('#fullscreen3DBtn').click();
      }
      if (layout === 'mobile') await page.setViewportSize({ width: 390, height: 844 });
      await page.waitForTimeout(200);
      const checks = await page.evaluate(() => {
        setCameraMode('human');
        const originalScene = three.scene, originalMirrors = three.mirrors;
        const results = [];
        try {
          three.scene = new THREE.Scene();
          three.scene.background = new THREE.Color(0);
          three.mirrors = [];
          // Known angles test the shader, cube-face orientation, and camera pose together.
          const angles = [[0, 0], [-109, 0], [109, 0], [-100, 0], [100, 0],
            [0, -74], [0, 74], [-95, 60], [95, -60]];
          for (const [yaw, pitch] of [[Math.PI, 0], [0.7, -0.3]]) {
            three.orbit.position.set(3, 1.5, 4);
            three.orbit.yaw = yaw; three.orbit.pitch = pitch;
            updateCamera();
            const markers = angles.map(([h, v]) => {
              const a = h * Math.PI / 180, b = v * Math.PI / 180;
              const marker = new THREE.Mesh(new THREE.SphereGeometry(.08, 12, 8),
                new THREE.MeshBasicMaterial({ color: 0xff0000 }));
              marker.position.set(Math.sin(a) * Math.cos(b), Math.sin(b), -Math.cos(a) * Math.cos(b))
                .multiplyScalar(10).applyQuaternion(three.camera.quaternion).add(three.camera.position);
              three.scene.add(marker);
              return marker;
            });
            updateCamera();
            const gl = three.renderer.getContext(), w = gl.drawingBufferWidth, h = gl.drawingBufferHeight;
            for (const [horizontal, vertical] of angles) {
              const x = Math.floor((horizontal / 220 + .5) * w);
              const y = Math.floor((vertical / 150 + .5) * h);
              const pixel = new Uint8Array(4);
              gl.readPixels(x, y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
              results.push({ horizontal, vertical, yaw, pitch, pixel: [...pixel] });
            }
            for (const marker of markers) {
              three.scene.remove(marker); marker.geometry.dispose(); marker.material.dispose();
            }
          }
        } finally {
          three.scene = originalScene; three.mirrors = originalMirrors;
        }
        return results;
      });
      for (const check of checks) assert(check.pixel[0] > 200 && check.pixel[1] < 20, JSON.stringify({ layout, ...check }));
      const house = await page.evaluate(() => {
        state.viewFloor = 'all';
        els.viewFloorSelect.value = 'all';
        three.orbit.position.set(-5, 1.5, 12);
        three.orbit.yaw = 2.4; three.orbit.pitch = -.1;
        render3D();
        const gl = three.renderer.getContext();
        const pixels = new Uint8Array(gl.drawingBufferWidth * gl.drawingBufferHeight * 4);
        gl.readPixels(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
        const colors = new Set();
        for (let i = 0; i < pixels.length; i += 64) colors.add(`${pixels[i]},${pixels[i + 1]},${pixels[i + 2]}`);
        const initialY = three.orbit.position.y;
        moveCameraByKey('w', false, 10000);
        const afterY = three.orbit.position.y;
        return { colors: colors.size, initialY, afterY, mirrors: three.mirrors.length };
      });
      assert(house.colors > 20, JSON.stringify(house));
      assert.equal(house.initialY, house.afterY, 'W movement must remain horizontal');
      await page.screenshot({ path: path.join(output, `${layout}.png`) });
      const fixed = await page.evaluate(() => {
        setCameraMode('fixed');
        const rect = threeCanvas.getBoundingClientRect();
        return { actual: three.camera.fov, expected: humanVerticalFov(100, fixedCameraBaselineAspect(rect)) };
      });
      assert(Math.abs(fixed.actual - fixed.expected) < 1e-8);
      await page.evaluate(() => setCameraMode('human'));
      console.log(JSON.stringify({ layout, angularChecks: checks.length, house, fixed }));
    }
    const reflection = await page.evaluate(() => {
      const mirror = three.mirrors[0];
      if (!mirror) return null;
      three.scene.updateMatrixWorld(true);
      const position = new THREE.Vector3().setFromMatrixPosition(mirror.surface.matrixWorld);
      const normal = new THREE.Vector3(0, 0, 1).transformDirection(mirror.surface.matrixWorld);
      three.orbit.position.copy(position).addScaledVector(normal, 1.4);
      const direction = normal.clone().negate();
      three.orbit.yaw = Math.atan2(direction.x, direction.z);
      three.orbit.pitch = 0;
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
    console.log(JSON.stringify({ reflection }));
    assert.deepEqual(errors, []);
    console.log('Panorama projection, resize, fixed-scale mode and navigation passed.');
  } finally {
    await browser?.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
