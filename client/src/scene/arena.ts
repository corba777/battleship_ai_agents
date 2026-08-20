import * as THREE from "three";
import { Board } from "./board";
import { CameraDirector } from "./cameras";
import { Heatmap } from "./heatmap";
import { Pegs } from "./pegs";
import { Fleet } from "./ships";
import { Ocean, makeSky } from "./water";
import type { Belief, ShipPlacement, ShotKind, Side } from "../types";

export interface SideView {
  board: Board;
  fleet: Fleet;
  pegs: Pegs;
  heatmap: Heatmap;
}

export class Arena {
  readonly scene = new THREE.Scene();
  readonly camera: THREE.PerspectiveCamera;
  readonly renderer: THREE.WebGLRenderer;
  readonly director: CameraDirector;
  readonly sides: Record<Side, SideView>;
  private readonly clock = new THREE.Clock();
  private readonly ocean = new Ocean();

  constructor(canvas: HTMLCanvasElement) {
    this.scene.background = new THREE.Color(0x1c242c);
    this.scene.fog = new THREE.FogExp2(0x1c242c, 0.01);

    this.camera = new THREE.PerspectiveCamera(46, 1, 0.1, 200);
    this.director = new CameraDirector(this.camera);

    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.18;

    this.scene.add(makeSky());
    this.scene.add(this.ocean.mesh);
    this.addLights();

    const left = this.makeSide("left", -9.2, 0.1);
    const right = this.makeSide("right", 9.2, -0.1);
    this.sides = { left, right };

    window.addEventListener("resize", () => this.resize());
    this.resize();
  }

  private makeSide(side: Side, x: number, yaw: number): SideView {
    const board = new Board(side);
    board.setRest(x, 0.7, 0);
    board.group.rotation.set(-0.14, yaw, 0);
    this.scene.add(board.group);
    return {
      board,
      fleet: new Fleet(board),
      pegs: new Pegs(board),
      heatmap: new Heatmap(board),
    };
  }

  private addLights(): void {
    const hemi = new THREE.HemisphereLight(0xd8dde4, 0x3a4a52, 0.85);
    this.scene.add(hemi);

    const sun = new THREE.DirectionalLight(0xf2efe6, 1.4);
    sun.position.set(8, 18, 12);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.camera.near = 1;
    sun.shadow.camera.far = 50;
    sun.shadow.camera.left = -20;
    sun.shadow.camera.right = 20;
    sun.shadow.camera.top = 20;
    sun.shadow.camera.bottom = -20;
    this.scene.add(sun);

    const fill = new THREE.DirectionalLight(0x8a9aaa, 0.35);
    fill.position.set(-12, 6, -4);
    this.scene.add(fill);
  }

  placeShips(side: Side, ships: ShipPlacement[]): void {
    this.sides[side].fleet.load(ships);
  }

  revealShip(side: Side, ship: ShipPlacement): void {
    this.sides[side].fleet.add(ship);
  }

  clearHeatmaps(): void {
    this.sides.left.heatmap.clear();
    this.sides.right.heatmap.clear();
  }

  setBelief(target: Side, belief: Belief[]): void {
    this.clearHeatmaps();
    this.sides[target].heatmap.set(belief);
  }

  peg(target: Side, cell: string, kind: ShotKind): void {
    this.sides[target].pegs.place(cell, kind);
    if (kind === "repeat") this.sides[target].board.bump();
  }

  sink(owner: Side, name: string): void {
    this.sides[owner].fleet.markSunk(name);
  }

  focusBoard(side: Side): void {
    this.director.focus(side);
  }

  focusCell(side: Side, cell: string): void {
    const world = this.sides[side].board.cellWorld(cell, 0.2);
    this.director.focus(side, world ?? undefined);
  }

  reset(): void {
    for (const side of ["left", "right"] as const) {
      this.sides[side].fleet.clear();
      this.sides[side].pegs.clear();
      this.sides[side].heatmap.clear();
    }
    this.director.idle();
  }

  pick(ndc: THREE.Vector2): { side: Side; cell: string } | null {
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(ndc, this.camera);
    for (const side of ["left", "right"] as const) {
      const cell = this.sides[side].board.pick(raycaster);
      if (cell) return { side, cell };
    }
    return null;
  }

  tick(): void {
    const dt = Math.min(this.clock.getDelta(), 0.05);
    this.ocean.update(this.clock.elapsedTime);
    this.sides.left.board.update(dt);
    this.sides.right.board.update(dt);
    this.director.update(dt);
    this.renderer.render(this.scene, this.camera);
  }

  private resize(): void {
    const w = window.innerWidth;
    const h = window.innerHeight;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }
}
