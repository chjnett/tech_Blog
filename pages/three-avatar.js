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
camera.position.set(0, 1.05, 2.9);
camera.lookAt(0, 0.9, -0.2);

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
  // 코드 블록 스타일: #10131A 배경 + 상단 바(라벨) + 모노 텍스트
  tctx.fillStyle = '#10131A';
  tctx.fillRect(0, 0, termCanvas.width, termCanvas.height);
  // 상단 바 (코드 블록 .code-bar처럼)
  tctx.fillStyle = 'rgba(255,255,255,0.04)';
  tctx.fillRect(0, 0, termCanvas.width, 22);
  tctx.fillStyle = 'rgba(255,255,255,0.08)';
  tctx.fillRect(0, 22, termCanvas.width, 1);
  tctx.font = '11px "JetBrains Mono", ui-monospace, monospace';
  tctx.fillStyle = 'rgba(246,247,249,0.5)';
  tctx.textAlign = 'right';
  tctx.fillText('python', termCanvas.width - 14, 15);
  tctx.textAlign = 'left';
  // 코드 줄
  tctx.font = '13px "JetBrains Mono", ui-monospace, monospace';
  TERM_LINES.slice(0, termLine + 1).forEach((line, i) => {
    tctx.fillStyle = line.startsWith('$') ? '#F6F7F9' : '#7A8290';
    tctx.fillText(line, 14, 42 + i * 17);
  });
  if (Math.floor(Date.now() / 700) % 2 === 0) {
    tctx.fillStyle = '#F6F7F9';
    tctx.fillRect(14 + tctx.measureText('$ python train.py').width + 6, 32, 8, 16);
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

// ── 책상 + 키보드 (아바타 손 위치에 가깝게) ──
scene.add(box(2.2, 0.09, 0.9, LINE, 0, 0.85, 0.3));
scene.add(box(0.09, 0.8, 0.7, INK_SOFT, -1.0, 0.45, 0.3));
scene.add(box(0.09, 0.8, 0.7, INK_SOFT, 1.0, 0.45, 0.3));
scene.add(box(0.5, 0.03, 0.18, INK_SOFT, 0, 0.9, 0.45));

// ── 아바타 로드 ──
const gltfLoader = new GLTFLoader();
const fbxLoader = new FBXLoader();

const [gltf, idleObj, typingObj] = await Promise.all([
  gltfLoader.loadAsync('/3d/avatar.glb'),
  fbxLoader.loadAsync('/3d/idle.fbx'),
  fbxLoader.loadAsync('/3d/typing.fbx'),
]);

const avatar = gltf.scene;
// 디자인 시스템 캐릭터: 실사 재질 제거 → 톤(셀) 셰이딩 + 블로그 팔레트 단색
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
function toonMat(color) {
  return new THREE.MeshToonMaterial({ color, gradientMap: null });
}
avatar.traverse((o) => {
  if (o.isMesh) {
    const c = MAT_MAP[o.material && o.material.name];
    o.material = toonMat(c !== undefined ? c : BG_SOFT);
  }
});
avatar.position.set(0, -0.15, -0.25);
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

// ── 떠다니는 코드 큐브 (무채색, 2개로 간결하게) ──
const cubes = [];
const cubeData = [
  { p: [-1.3, 1.85, 0.1], s: 0.13, c: INK },
  { p: [1.3, 1.7, 0.2], s: 0.09, c: INK_SOFT },
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
  // getDelta()를 먼저 호출해야 애니메이션이 진행된다
  // (getElapsedTime()은 내부적으로 getDelta()를 소모하므로 순서 주의)
  const dt = clock.getDelta();
  const t = clock.elapsedTime;

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
