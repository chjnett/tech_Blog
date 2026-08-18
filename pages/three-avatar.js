// 홈 hero 3D — Ready Player Me 스타일 아바타가 코딩하는 모습 (vanilla three.js).
// 참고: github.com/rohan300/3d-avatar-render (Idle/Typing FBX + 마우스 헤드 트래킹 로직)
// 디자인 시스템: 모노크롬 머티리얼(흰/회색/검정)만 사용.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { FBXLoader } from 'three/addons/loaders/FBXLoader.js';

const canvas = document.getElementById('hero3d');
if (!canvas) throw new Error('no canvas');
const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ── 팔레트 (블로그 디자인 시스템) ──
const INK = 0x10131a;
const INK_SOFT = 0x5b6270;
const LINE = 0xe7e9ee;
const BG_SOFT = 0xf6f7f9;
const WHITE = 0xffffff;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 60);
camera.position.set(0, 1.2, 2.9);
camera.lookAt(0, 1.05, -0.2);

const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
renderer.setClearColor(0x000000, 0);
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.shadowMap.enabled = false;

scene.add(new THREE.AmbientLight(WHITE, 1.5));
const dir = new THREE.DirectionalLight(WHITE, 1.0);
dir.position.set(3, 6, 4);
scene.add(dir);
const rim = new THREE.DirectionalLight(WHITE, 0.6);
rim.position.set(-3, 4, -4);
scene.add(rim);

const mat = (c, extra) =>
  new THREE.MeshStandardMaterial(Object.assign({ color: c, roughness: 0.7, metalness: 0.05 }, extra || {}));

function box(w, h, d, color, x, y, z, extra) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat(color, extra));
  m.position.set(x || 0, y || 0, z || 0);
  return m;
}

// ── 뒷벽 터미널 ──
const bezel = new THREE.Mesh(new THREE.PlaneGeometry(1.7, 1.05), new THREE.MeshBasicMaterial({ color: INK }));
bezel.position.set(0, 1.75, -1.35);
scene.add(bezel);

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
const screen = new THREE.Mesh(new THREE.PlaneGeometry(1.6, 0.97), new THREE.MeshBasicMaterial({ map: termTex }));
screen.position.set(0, 1.75, -1.32);
scene.add(screen);
drawTerminal();

// ── 책상 + 키보드 ──
scene.add(box(2.2, 0.09, 0.9, LINE, 0, 1.0, 0));
scene.add(box(0.09, 0.95, 0.7, INK_SOFT, -1.0, 0.52, 0));
scene.add(box(0.09, 0.95, 0.7, INK_SOFT, 1.0, 0.52, 0));
scene.add(box(0.5, 0.03, 0.18, INK_SOFT, 0, 1.07, 0.32));

// ── 아바타 로드 ──
const gltfLoader = new GLTFLoader();
const fbxLoader = new FBXLoader();

const [gltf, idleObj, typingObj] = await Promise.all([
  gltfLoader.loadAsync('/3d/avatar.glb'),
  fbxLoader.loadAsync('/3d/idle.fbx'),
  fbxLoader.loadAsync('/3d/typing.fbx'),
]);

const avatar = gltf.scene;
// 모노크롬 머티리얼로 교체 (텍스처 대신 팔레트 단색)
const MAT_MAP = {
  Wolf3D_Skin: BG_SOFT,
  Wolf3D_Teeth: WHITE,
  Wolf3D_Hair: INK,
  Wolf3D_Body: LINE,
  Wolf3D_Outfit_Top: INK_SOFT,
  Wolf3D_Outfit_Bottom: INK_SOFT,
  Wolf3D_Outfit_Footwear: INK,
  Wolf3D_Eye: INK,
};
avatar.traverse((o) => {
  if (o.isMesh) {
    const c = MAT_MAP[o.material && o.material.name];
    o.material = new THREE.MeshStandardMaterial({
      color: c !== undefined ? c : BG_SOFT,
      roughness: 0.75,
      metalness: 0.0,
    });
  }
});
avatar.position.set(0, 0, -0.25);
scene.add(avatar);

// ── 애니메이션 ──
const mixer = new THREE.AnimationMixer(avatar);
const idleClip = idleObj.animations[0];
const typingClip = typingObj.animations[0];
if (idleClip) idleClip.name = 'idle';
if (typingClip) typingClip.name = 'typing';
const idleAction = mixer.clipAction(idleClip);
const typingAction = mixer.clipAction(typingClip);
idleAction.play();
let mode = 'idle';
let animStart = performance.now();

// ── 마우스 헤드 트래킹 (subtle) ──
const mouse = { x: 0, y: 0 };
const head = avatar.getObjectByName('Head');
let headTarget = new THREE.Vector3(0, 1.4, 0);
window.addEventListener('pointermove', (e) => {
  mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
  mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
});
window.addEventListener('pointerleave', () => { mouse.x = 0; mouse.y = 0; });

// ── 떠다니는 코드 큐브 ──
const cubes = [];
const cubeData = [
  { p: [-1.35, 1.7, 0.15], s: 0.14, c: INK },
  { p: [1.35, 1.9, -0.1], s: 0.1, c: INK_SOFT },
  { p: [-1.15, 2.05, -0.3], s: 0.08, c: LINE },
  { p: [1.15, 1.5, 0.3], s: 0.12, c: INK },
];
cubeData.forEach((d) => {
  const cube = box(d.s, d.s, d.s, d.c, d.p[0], d.p[1], d.p[2]);
  cube.userData = { baseY: d.p[1], phase: Math.random() * Math.PI * 2 };
  scene.add(cube);
  cubes.push(cube);
});

// ── 크기 ──
function resize() {
  const w = canvas.clientWidth || 320;
  const h = canvas.clientHeight || 300;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
resize();
window.addEventListener('resize', resize);

// ── 루프 ──
const clock = new THREE.Clock();
let frame = 0;
function tick() {
  frame++;
  const t = clock.getElapsedTime();
  const dt = clock.getDelta();

  // Idle → Typing 전환 (1.8초 후)
  if (!reduced && mode === 'idle' && performance.now() - animStart > 1800) {
    mode = 'typing';
    typingAction.reset().fadeIn(0.5).play();
    idleAction.fadeOut(0.5);
  }

  // 터미널 줄 진행
  if (!reduced && Math.floor(t / 1.6) > termLine) {
    termLine = Math.min(termLine + 1, TERM_LINES.length - 1);
    drawTerminal();
  }
  if (frame % 12 === 0) drawTerminal();

  // 헤드 트래킹 (부드럽게)
  if (head && !reduced) {
    headTarget.set(mouse.x * 1.2, 1.4 + mouse.y * 0.6, 1.2);
    head.lookAt(headTarget);
  }

  // 큐브
  cubes.forEach((c) => {
    c.position.y = c.userData.baseY + Math.sin(t * 1.1 + c.userData.phase) * 0.06;
    c.rotation.x += 0.004;
    c.rotation.y += 0.006;
  });

  mixer.update(dt);
  renderer.render(scene, camera);
  if (!reduced) requestAnimationFrame(tick);
}

if (reduced) {
  // 정적: Idle 자세 한 프레임
  if (idleAction) { idleAction.play(); mixer.update(0.1); }
  renderer.render(scene, camera);
} else {
  requestAnimationFrame(tick);
}
