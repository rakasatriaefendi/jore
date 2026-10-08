import { workstations } from '../scene/officeLayout';

export function OfficeKey() {
  return (
    <aside className="office-key" aria-label="Office workstations">
      <h2>Workstations</h2>
      <ul>
        {workstations.map(({ name, location, accent }) => (
          <li key={name}>
            <span
              className="office-key-swatch"
              style={{ backgroundColor: accent.color.getStyle() }}
            />
            <span>{name}</span>
            <span className="office-key-location">{location}</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}
