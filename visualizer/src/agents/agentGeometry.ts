import { MeshStandardMaterial, SphereGeometry, TorusGeometry } from 'three';

export const headGeometry = new SphereGeometry(1, 8, 6);
export const selectionRingGeometry = new TorusGeometry(0.31, 0.025, 5, 24);
export const uniformMaterial = new MeshStandardMaterial({
  color: '#545866',
  roughness: 0.82,
});
