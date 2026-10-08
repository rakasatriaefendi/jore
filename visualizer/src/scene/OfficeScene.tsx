import { Agents } from '../agents/Agents';
import { OfficeFixtures } from '../environment/OfficeFixtures';
import { OfficeRoom } from '../environment/OfficeRoom';
import { Workstation } from '../environment/Workstation';
import { workstations } from './officeLayout';

interface OfficeSceneProps {
  selectedAgentId: string | null;
  onSelectAgent: (id: string) => void;
}

export function OfficeScene({
  selectedAgentId,
  onSelectAgent,
}: OfficeSceneProps) {
  return (
    <>
      <color attach="background" args={['#121218']} />
      <hemisphereLight args={['#e5e5f0', '#3b3541', 2.1]} />
      <directionalLight position={[4, 9, 6]} intensity={2.1} />
      <OfficeRoom />
      <OfficeFixtures />
      {workstations.map(({ name, position, accent, supervisor }) => (
        <Workstation
          key={name}
          name={name}
          position={[...position]}
          accent={accent}
          supervisor={supervisor}
        />
      ))}
      <Agents selectedAgentId={selectedAgentId} onSelectAgent={onSelectAgent} />
    </>
  );
}
