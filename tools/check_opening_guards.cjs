const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const server = http.createServer((req, res) => {
  if (req.url === '/favicon.ico') return res.writeHead(204).end();
  res.setHeader('Content-Type', 'text/html');
  res.end(fs.readFileSync(path.join(root, 'index.html')));
});
(async () => {
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  let browser;
  try {
    browser = await chromium.launch({headless:true,channel:'chrome'});
    const page = await browser.newPage({viewport:{width:1600,height:1000}});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    await page.waitForFunction(() => typeof three !== 'undefined' && three.isReady);
    const output = path.join(root,'pdf_renders/opening-guards');
    fs.mkdirSync(output,{recursive:true});
    for (const n of [3,4,5]) {
      const plan = JSON.parse(fs.readFileSync(path.join(root,`plans/architect-alt-${n}-v2.json`)));
      await page.evaluate(p => applyPlanSnapshot(p),plan);
      for (const floor of ['ground','living']) {
        const result = await page.evaluate(({n,floor}) => {
          const id=`architect-alt-${n}-v2-${floor}`;
          state.activeFloorId=id; state.viewFloor=id; els.viewFloorSelect.value=id;
          const guards=state.walls.filter(w=>w.floorId===id && w.openingGuard);
          const level=state.floors.find(f=>f.id===id).elevation;
          const xs=guards.map(g=>g.x+g.w/2), ys=guards.map(g=>g.y+g.h/2);
          const cx=(Math.min(...xs)+Math.max(...xs))/2, cy=(Math.min(...ys)+Math.max(...ys))/2;
          const screen=canvas.getBoundingClientRect();
          state.scale=55; state.offset={x:screen.width/2-cx*55,y:screen.height/2-cy*55};
          three.orbit.position.set(cx,level+6,cy+6);
          three.orbit.yaw=Math.PI; three.orbit.pitch=-.75;
          renderAll();
          three.root.traverse(mesh => {
            if (mesh.userData.storySurface === 'ceiling' || mesh.userData.roofId) mesh.visible=false;
          });
          updateCamera();
          const groups=three.root.children.filter(g=>g.userData.openingGuard);
          const heights=groups.map(g=>new THREE.Box3().setFromObject(g).max.y-level);
          const gl=three.renderer.getContext();
          const pixels=new Uint8Array(gl.drawingBufferWidth*gl.drawingBufferHeight*4);
          gl.readPixels(0,0,gl.drawingBufferWidth,gl.drawingBufferHeight,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
          const colors=new Set();
          for(let i=0;i<pixels.length;i+=64) colors.add(`${pixels[i]},${pixels[i+1]},${pixels[i+2]}`);
          return {expected:guards.length,count:groups.length,heights,colors:colors.size,
            materials:groups.every(g=>g.children[0].material.transparent && g.children[1].material.color.getHexString()==='a08060')};
        },{n,floor});
        assert(result.expected>0 && result.count===result.expected,JSON.stringify({n,floor,...result}));
        assert(result.materials && result.colors>30);
        result.heights.forEach(h=>assert(Math.abs(h-.9)<.0001));
        await page.screenshot({path:path.join(output,`alt${n}-${floor}.png`)});
        console.log(n,floor,result.count,'guards verified');
      }
    }
    await page.setViewportSize({width:390,height:844});
    await page.evaluate(() => { els.viewShell.requestFullscreen=undefined; });
    await page.locator('#fullscreen3DBtn').click();
    await page.waitForTimeout(200);
    await page.evaluate(() => {
      three.root.traverse(mesh => {
        if (mesh.userData.storySurface === 'ceiling' || mesh.userData.roofId) mesh.visible=false;
      });
      updateCamera();
    });
    await page.screenshot({path:path.join(output,'mobile.png')});
    assert.deepEqual(errors,[]);
  } finally {
    await browser?.close();
    await new Promise(r=>server.close(r));
  }
})().catch(e=>{ console.error(e); process.exitCode=1; });
