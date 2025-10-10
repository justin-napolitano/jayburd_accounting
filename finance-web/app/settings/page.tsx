export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Settings</h1>
      <div className="card space-y-3">
        <div className="flex items-center gap-3">
          <label className="w-48 text-neutral-300">Timezone</label>
          <input className="input" defaultValue="America/New_York" />
        </div>
        <div className="flex items-center gap-3">
          <label className="w-48 text-neutral-300">Currency</label>
          <input className="input" defaultValue="USD" />
        </div>
      </div>
    </div>
  );
}
