import * as THREE from "three";
import type { Side } from "../types";

export type Rig = "idle" | "focus" | "finale";

const IDLE_HEIGHT = 17.2;
const IDLE_Z = 14.8;
const FOCUS_HEIGHT = 16.4;
const FOCUS_Z = 13.2;
/** Camera slides this far opposite the target board so the yaw reads. */
const FOCUS_X = 8.4;

export class CameraDirector {
  private rig: Rig = "idle";
  private theta = 0.18;
  private readonly look = new THREE.Vector3(0, 0.6, 0);
  private readonly desired = new THREE.Vector3();
  private readonly desiredLook = new THREE.Vector3(0, 0.6, 0);
  private finaleT = 0;

  constructor(private readonly camera: THREE.PerspectiveCamera) {
    this.camera.position.set(0, IDLE_HEIGHT, IDLE_Z);
    this.camera.lookAt(this.look);
  }

  idle(): void {
    this.rig = "idle";
  }

  /** Swing toward `target` (the board being shot at). Optional cell nudges the look. */
  focus(target: Side, cellWorld?: THREE.Vector3): void {
    this.rig = "focus";
    const toward = target === "right" ? 1 : -1;
    this.desired.set(-toward * FOCUS_X, FOCUS_HEIGHT, FOCUS_Z);
    const lookX = toward * 9.2;
    const lookZ = cellWorld?.z ?? 0;
    this.desiredLook.set(lookX, 0.7, lookZ * 0.35);
    if (cellWorld) {
      this.desiredLook.x = THREE.MathUtils.lerp(lookX, cellWorld.x, 0.28);
      this.desired.x += (cellWorld.x - lookX) * 0.08;
    }
  }

  finale(): void {
    this.rig = "finale";
    this.finaleT = 0;
  }

  get mode(): Rig {
    return this.rig;
  }

  update(dt: number): void {
    if (this.rig === "idle") {
      this.theta += dt * 0.08;
      const sway = Math.sin(this.theta) * 0.22;
      this.desired.set(Math.sin(sway) * 1.2, IDLE_HEIGHT, IDLE_Z);
      this.desiredLook.set(0, 0.55, 0);
    } else if (this.rig === "finale") {
      this.finaleT += dt * 0.1;
      const t = this.finaleT;
      this.desired.set(Math.sin(t) * 5, 16 + Math.sin(t * 0.5) * 1.2, 14);
      this.desiredLook.set(Math.sin(t * 0.35) * 2, 0.5, 0);
    }

    const posK = this.rig === "focus" ? 1.6 : 2.2;
    this.camera.position.lerp(this.desired, 1 - Math.exp(-dt * posK));
    this.look.lerp(this.desiredLook, 1 - Math.exp(-dt * 2.4));
    this.camera.lookAt(this.look);
  }
}
