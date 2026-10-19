import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { pose } from './lib/motion.js';
import { ddsTexture } from './lib/textures.js';
export class Comparison {
  constructor(canvas) {
    this.canvas = canvas;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.setClearColor(0x111a29);
    this.camera = new THREE.PerspectiveCamera(34, 2, 0.01, 100);
    this.camera.position.set(0, 1.2, 6);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.target.set(0, 0.8, 0);
    this.controls.update();
    this.scenes = [];
    this.motion = null;
    this.time = 0;
    this.playing = true;
    this.speed = 1;
    this.last = performance.now();
    this.tick = this.tick.bind(this);
    requestAnimationFrame(this.tick);
  }
  clear() {
    for (const entry of this.scenes) {
      entry.scene.traverse((object) => {
        object.geometry?.dispose();
        if (object.material) object.material.dispose();
      });
      entry.skeleton?.dispose();
      for (const texture of entry.textures) texture.dispose();
    }
    this.scenes = [];
  }
  set(reference, converted) {
    this.clear();
    for (const asset of [reference, converted]) {
      const scene = new THREE.Scene(),
        meshes = [],
        textures = asset ? asset.model.names.map((n) => ddsTexture(asset.textures.get(n))) : [],
        bones = asset
          ? asset.model.bones.map((b) => {
              const bone = new THREE.Bone();
              bone.matrixWorld.fromArray(b.matrix);
              return bone;
            })
          : [],
        skeleton = asset
          ? new THREE.Skeleton(
              bones,
              asset.model.bones.map((b) => new THREE.Matrix4().fromArray(b.inverse)),
            )
          : null;
      const grid = new THREE.GridHelper(6, 24, 0x3b526d, 0x24334a);
      scene.add(grid);
      if (asset)
        for (const packet of asset.model.packets) {
          const g = new THREE.BufferGeometry();
          g.setAttribute(
            'position',
            new THREE.Float32BufferAttribute(
              packet.vertices.flatMap((v) => v.position),
              3,
            ),
          );
          g.setAttribute(
            'uv',
            new THREE.Float32BufferAttribute(
              packet.vertices.flatMap((v) => v.uv),
              2,
            ),
          );
          g.setAttribute(
            'skinIndex',
            new THREE.Uint16BufferAttribute(
              packet.vertices.flatMap((v) => v.ids),
              4,
            ),
          );
          g.setAttribute(
            'skinWeight',
            new THREE.Float32BufferAttribute(
              packet.vertices.flatMap((v) => v.weights),
              4,
            ),
          );
          g.setIndex(packet.indices);
          const mesh = new THREE.SkinnedMesh(
            g,
            new THREE.MeshBasicMaterial({
              map: textures[packet.texture],
              side: THREE.DoubleSide,
              alphaTest: 0.39,
            }),
          );
          mesh.bind(skeleton, new THREE.Matrix4());
          mesh.frustumCulled = false;
          scene.add(mesh);
          meshes.push(mesh);
        }
      this.scenes.push({ asset, scene, meshes, textures, bones, skeleton });
    }
    this.time = 0;
  }
  tick(now) {
    const elapsed = Math.min(0.1, (now - this.last) / 1000);
    this.last = now;
    if (this.playing && this.motion)
      this.time = (this.time + elapsed * this.speed) % ((this.motion.last + 1) / 60);
    const width = this.canvas.clientWidth,
      height = this.canvas.clientHeight;
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / 2 / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setScissorTest(true);
    this.scenes.forEach((entry, side) => {
      if (entry.asset) {
        const world = pose(entry.asset.model, this.motion, this.time * 60);
        entry.bones.forEach((bone, i) => bone.matrixWorld.copy(world[i]));
        entry.skeleton.update();
      }
      this.renderer.setViewport((side * width) / 2, 0, width / 2, height);
      this.renderer.setScissor((side * width) / 2, 0, width / 2, height);
      this.renderer.render(entry.scene, this.camera);
    });
    this.onTime?.(this.time);
    requestAnimationFrame(this.tick);
  }
}
