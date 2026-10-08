import { BoxGeometry, MeshStandardMaterial } from 'three';

export const cube = new BoxGeometry(1, 1, 1);

// Static prototype geometry and materials are shared by every office component.
export const materials = {
  floor: new MeshStandardMaterial({ color: '#33313b', roughness: 0.9 }),
  tile: new MeshStandardMaterial({ color: '#3c3943', roughness: 0.92 }),
  wall: new MeshStandardMaterial({ color: '#494650', roughness: 0.86 }),
  trim: new MeshStandardMaterial({ color: '#615b65', roughness: 0.7 }),
  desk: new MeshStandardMaterial({ color: '#747078', roughness: 0.77 }),
  frame: new MeshStandardMaterial({ color: '#292b35', roughness: 0.72 }),
  seat: new MeshStandardMaterial({ color: '#424650', roughness: 0.88 }),
  screen: new MeshStandardMaterial({ color: '#76959c', roughness: 0.35 }),
  board: new MeshStandardMaterial({ color: '#d9d6d2', roughness: 0.83 }),
  paper: new MeshStandardMaterial({ color: '#ada6a1', roughness: 0.95 }),
  pink: new MeshStandardMaterial({ color: '#dd78a6', roughness: 0.7 }),
  blue: new MeshStandardMaterial({ color: '#6e9eb8', roughness: 0.7 }),
  green: new MeshStandardMaterial({ color: '#8ba993', roughness: 0.7 }),
  amber: new MeshStandardMaterial({ color: '#c4a273', roughness: 0.7 }),
  violet: new MeshStandardMaterial({ color: '#a78fb9', roughness: 0.7 }),
};
