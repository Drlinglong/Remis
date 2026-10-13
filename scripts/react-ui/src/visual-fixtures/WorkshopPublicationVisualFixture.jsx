import WorkshopPublicationPanel from '../components/steamWorkshop/publication/WorkshopPublicationPanel';

export default function WorkshopPublicationVisualFixture() {
  return <main data-remis-surface="canvas" style={{ padding: 24 }}>
    <WorkshopPublicationPanel workspaceId="visual-publication" />
  </main>;
}
