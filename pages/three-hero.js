// 홈 hero 3D 장면 — 블로그 디자인 시스템(모노크롬)의 캐릭터가 코딩하는 모습.
// three.js(CDN) 사용, 색은 블로그 팔레트(ink/ink-soft/line/bg-soft/white)만 쓴다.
(function () {
  const canvas = document.getElementById('hero3d');
  if (!canvas) return;
  if (typeof THREE === 'undefined') return;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const INK = 0x10131a;
  const INK_SOFT = 0x5b6270;
  const LINE = 0xe7e9ee;
  const BG_SOFT = 0xf6f7f9;
  const WHITE = 0xffffff;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 60);
  camera.position.set(0, 1.75, 4.9);
  camera.lookAt(0, 1.15, -0.3);

  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

  // 조명은 전부 흰색(모노크롬 유지)
  scene.add(new THREE.AmbientLight(WHITE, 1.2));
  const dir = new THREE.DirectionalLight(WHITE, 0.9);
  dir.position.set(3, 6, 4);
  scene.add(dir);
  const fill = new THREE.DirectionalLight(WHITE, 0.3);
  fill.position.set(-4, 2, -3);
  scene.add(fill);

  const mat = (c, extra) =>
    new THREE.MeshStandardMaterial(Object.assign({ color: c, roughness: 0.65, metalness: 0.05 }, extra || {}));

  function box(w, h, d, color, x, y, z, extra) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat(color, extra));
    m.position.set(x || 0, y || 0, z || 0);
    return m;
  }

  const world = new THREE.Group();
  scene.add(world);

  // ── 뒷벽 터미널 (큰 화면) ──
  const bezel = new THREE.Mesh(
    new THREE.PlaneGeometry(2.3, 1.4),
    new THREE.MeshBasicMaterial({ color: INK })
  );
  bezel.position.set(0, 1.75, -1.05);
  world.add(bezel);

  const termCanvas = document.createElement('canvas');
  termCanvas.width = 320;
  termCanvas.height = 200;
  const tctx = termCanvas.getContext('2d');
  const TERM_LINES = [
    '$ python train.py',
    'epoch 1/10 | loss 4.21',
    'epoch 2/10 | loss 2.08',
    'epoch 3/10 | loss 1.37',
    'epoch 4/10 | loss 0.92',
    'epoch 5/10 | loss 0.64',
    'epoch 6/10 | loss 0.45',
    'epoch 7/10 | loss 0.33',
    'epoch 8/10 | loss 0.25',
    'epoch 9/10 | loss 0.19',
    'epoch 10/10 | loss 0.15',
    '✓ training done',
    '$ █',
  ];
  let termLine = 0;
  function drawTerminal() {
    tctx.fillStyle = '#10131A';
    tctx.fillRect(0, 0, termCanvas.width, termCanvas.height);
    tctx.font = '13px "JetBrains Mono", ui-monospace, monospace';
    TERM_LINES.slice(0, termLine + 1).forEach((line, i) => {
      tctx.fillStyle = line.startsWith('$') ? '#F6F7F9' : '#7A8290';
      tctx.fillText(line, 14, 22 + i * 17);
    });
    if (Math.floor(Date.now() / 700) % 2 === 0) {
      tctx.fillStyle = '#F6F7F9';
      tctx.fillRect(14 + tctx.measureText('$ python train.py').width + 6, 12, 8, 16);
    }
    if (termCanvas.__tex) termCanvas.__tex.needsUpdate = true;
  }
  const termTex = new THREE.CanvasTexture(termCanvas);
  termCanvas.__tex = termTex;
  termTex.minFilter = THREE.LinearFilter;
  const screen = new THREE.Mesh(
    new THREE.PlaneGeometry(2.18, 1.3),
    new THREE.MeshBasicMaterial({ map: termTex })
  );
  screen.position.set(0, 1.75, -1.02); // +z를 향해 카메라를 바라봄
  world.add(screen);
  drawTerminal();

  // ── 책상 ──
  world.add(box(2.5, 0.09, 1.0, LINE, 0, 1.0, 0));
  world.add(box(0.09, 0.95, 0.8, INK_SOFT, -1.15, 0.52, 0));
  world.add(box(0.09, 0.95, 0.8, INK_SOFT, 1.15, 0.52, 0));

  // ── 키보드 ──
  world.add(box(0.62, 0.03, 0.22, INK_SOFT, 0, 1.07, 0.42));

  // ── 캐릭터 (책상 뒤) ──
  const char = new THREE.Group();
  char.add(box(0.5, 0.6, 0.28, BG_SOFT, 0, 1.36, -0.15, { roughness: 0.85 }));
  char.add(box(0.1, 0.08, 0.1, INK_SOFT, 0, 1.66, -0.15));
  char.add(box(0.3, 0.3, 0.3, WHITE, 0, 1.85, -0.15, { roughness: 0.5 }));

  // 팔: 어깨에서 키보드 쪽으로 기울인 상자
  const armL = box(0.1, 0.55, 0.1, INK_SOFT, -0.3, 1.32, 0.08);
  const armR = box(0.1, 0.55, 0.1, INK_SOFT, 0.3, 1.32, 0.08);
  armL.rotation.x = 0.5;  // 어깨에서 키보드(전방) 쪽으로 기울임
  armR.rotation.x = 0.5;
  char.add(armL, armR);

  // 손: 키보드 위에서 타이핑
  const handL = new THREE.Group(); handL.position.set(-0.26, 1.12, 0.42);
  handL.add(box(0.11, 0.08, 0.12, INK, 0, 0, 0));
  const handR = new THREE.Group(); handR.position.set(0.26, 1.12, 0.42);
  handR.add(box(0.11, 0.08, 0.12, INK, 0, 0, 0));
  char.add(handL, handR);
  world.add(char);

  // ── 떠다니는 코드 큐브 (무채색 장식) ──
  const cubes = [];
  const cubeData = [
    { p: [-1.5, 1.85, 0.1], s: 0.15, c: INK },
    { p: [1.5, 2.0, -0.1], s: 0.11, c: INK_SOFT },
    { p: [-1.25, 2.15, -0.3], s: 0.09, c: LINE },
    { p: [1.3, 1.6, 0.25], s: 0.13, c: INK },
  ];
  cubeData.forEach((d) => {
    const cube = box(d.s, d.s, d.s, d.c, d.p[0], d.p[1], d.p[2]);
    cube.userData = { baseY: d.p[1], phase: Math.random() * Math.PI * 2 };
    world.add(cube);
    cubes.push(cube);
  });

  // ── 크기/카메라 ──
  function resize() {
    const w = canvas.clientWidth || 300;
    const h = canvas.clientHeight || 240;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  resize();
  window.addEventListener('resize', resize);

  // ── 애니메이션 ──
  const clock = new THREE.Clock();
  let frame = 0;
  function tick() {
    frame++;
    const t = clock.getElapsedTime();

    // 손 타이핑 (좌우 교차)
    const typing = Math.sin(t * 9);
    handL.position.y = 1.12 + Math.max(0, typing) * 0.035;
    handR.position.y = 1.12 + Math.max(0, -typing) * 0.035;

    // 캐릭터 숨쉬기
    char.position.y = Math.sin(t * 1.4) * 0.012;

    // 터미널 줄 진행
    if (Math.floor(t / 1.6) > termLine) {
      termLine = Math.min(termLine + 1, TERM_LINES.length - 1);
      drawTerminal();
    }
    if (frame % 12 === 0) drawTerminal();

    // 큐브 부유/회전
    cubes.forEach((c) => {
      c.position.y = c.userData.baseY + Math.sin(t * 1.1 + c.userData.phase) * 0.06;
      c.rotation.x += 0.004;
      c.rotation.y += 0.006;
    });

    // 미세 스웨이
    world.rotation.y = Math.sin(t * 0.35) * 0.06;

    renderer.render(scene, camera);
    if (!reduced) requestAnimationFrame(tick);
  }

  if (reduced) {
    renderer.render(scene, camera);
  } else {
    requestAnimationFrame(tick);
  }
})();
