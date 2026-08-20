import * as THREE from "three";

/** Flat water for now. A wave shader can come back once the rest of the scene is settled. */
export class Ocean {
  readonly mesh: THREE.Mesh;

  constructor() {
    this.mesh = new THREE.Mesh(
      new THREE.PlaneGeometry(140, 140),
      new THREE.MeshStandardMaterial({
        color: 0x1a5a72,
        roughness: 0.42,
        metalness: 0.28,
      }),
    );
    this.mesh.rotation.x = -Math.PI / 2;
    this.mesh.position.y = -0.12;
    this.mesh.receiveShadow = true;
  }

  update(_time: number): void {}
}

export function makeSky(): THREE.Mesh {
  const canvas = document.createElement("canvas");
  canvas.width = 8;
  canvas.height = 256;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("2d context unavailable");
  const grad = ctx.createLinearGradient(0, 0, 0, 256);
  grad.addColorStop(0, "#1a222c");
  grad.addColorStop(0.55, "#2a3340");
  grad.addColorStop(1, "#3a4450");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 8, 256);
  const map = new THREE.CanvasTexture(canvas);
  map.colorSpace = THREE.SRGBColorSpace;
  const mat = new THREE.MeshBasicMaterial({
    map,
    side: THREE.BackSide,
    depthWrite: false,
    fog: false,
    toneMapped: false,
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(80, 24, 16), mat);
  mesh.renderOrder = -1;
  return mesh;
}
