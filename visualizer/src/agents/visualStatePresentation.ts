import type { AgentVisualState } from './AgentVisualState';

interface Pose {
  lift: number;
  turn: number;
  lean: number;
  leftArm: number;
  rightArm: number;
  leftLeg: number;
  rightLeg: number;
  headTilt: number;
}

interface VisualStatePresentation {
  label: string;
  symbol: string;
  pose: Pose;
}

const neutral: Pose = {
  lift: 0,
  turn: 0,
  lean: 0,
  leftArm: 0.12,
  rightArm: -0.12,
  leftLeg: 0,
  rightLeg: 0,
  headTilt: 0,
};

// Static primitive poses and text symbols make states distinct without an animation loop.
export const visualStatePresentation: Record<
  AgentVisualState,
  VisualStatePresentation
> = {
  idle: { label: 'Idle', symbol: '○', pose: neutral },
  assigned: {
    label: 'Assigned',
    symbol: '◆',
    pose: { ...neutral, rightArm: -0.75, headTilt: 0.1 },
  },
  walking: {
    label: 'Walking',
    symbol: '➜',
    pose: {
      ...neutral,
      lift: 0.07,
      lean: 0.11,
      leftArm: 0.42,
      rightArm: -0.42,
      leftLeg: -0.3,
      rightLeg: 0.3,
    },
  },
  working: {
    label: 'Working',
    symbol: '⌨',
    pose: {
      ...neutral,
      turn: -2.1,
      lean: 0.15,
      leftArm: -0.55,
      rightArm: 0.55,
    },
  },
  waiting: {
    label: 'Waiting',
    symbol: 'Ⅱ',
    pose: { ...neutral, headTilt: -0.14, leftArm: 0.24, rightArm: -0.24 },
  },
  reviewing: {
    label: 'Reviewing',
    symbol: '☑',
    pose: { ...neutral, turn: 0.25, leftArm: 0.65, headTilt: 0.15 },
  },
  success: {
    label: 'Success',
    symbol: '✓',
    pose: {
      ...neutral,
      lift: 0.1,
      leftArm: 1.05,
      rightArm: -1.05,
      leftLeg: -0.1,
      rightLeg: 0.1,
    },
  },
  error: {
    label: 'Error',
    symbol: '!',
    pose: { ...neutral, lean: -0.16, headTilt: -0.3, rightArm: -0.6 },
  },
};
