import React from 'react';
import { Settings2 } from 'lucide-react';

export default function ControlPanelHome() {
  return (
    <div className="flex flex-col items-center justify-center py-32 text-center">
      <div className="bg-slate-100 dark:bg-zinc-900 p-4 rounded-full mb-4">
        <Settings2 size={40} className="text-slate-400 dark:text-zinc-500" />
      </div>
      <h1 className="text-2xl font-black text-slate-900 dark:text-zinc-100">Control Panel</h1>
      <p className="text-sm text-slate-500 dark:text-zinc-400 mt-2 max-w-md">
        Select an option from the menu to configure system settings, manage assets, and sync integrations.
      </p>
    </div>
  );
}