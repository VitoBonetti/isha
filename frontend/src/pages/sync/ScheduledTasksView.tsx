import React from 'react';
import {
  Metronome,
  Key,
  BookOpen,
  CloudSync,
  ShieldCheck,
  Database,
  Clock
} from 'lucide-react';

export default function ScheduledTaskView() {
  const tasks = [
    {
      title: "API Key Alert",
      description: "Checks all API keys and sends a notification to the user for any keys that are about to expire.",
      schedule: "Every day at 7:00 AM",
      timezone: "Amsterdam Time",
      icon: Key,
      iconColor: "text-amber-500",
      bgColor: "bg-amber-50 dark:bg-amber-900/20"
    },
    {
      title: "Daily RAG Update",
      description: "Checks for updates in the knowledge base folder and test folder to index new documents for the RAG.",
      schedule: "Every day at 5:00 AM",
      timezone: "Amsterdam Time",
      icon: BookOpen,
      iconColor: "text-purple-500",
      bgColor: "bg-purple-50 dark:bg-purple-900/20"
    },
    {
      title: "SNow Test RITM Sync",
      description: "Synchronizes the test requests (RITMs) on ServiceNow with the internal database and tests.",
      schedule: "Every day at 8:15 AM",
      timezone: "Amsterdam Time",
      icon: CloudSync,
      iconColor: "text-blue-500",
      bgColor: "bg-blue-50 dark:bg-blue-900/20"
    },
    {
      title: "Keep Secure 24 Automation",
      description: "Creates the tests on Keep Secure 24 for the current week's tests, provided all requirements are satisfied.",
      schedule: "Every Monday at 00:00",
      timezone: "Amsterdam Time",
      icon: ShieldCheck,
      iconColor: "text-emerald-500",
      bgColor: "bg-emerald-50 dark:bg-emerald-900/20"
    },
    {
      title: "SNow Asset Sync",
      description: "Synchronizes the asset database with the latest entries from ServiceNow.",
      schedule: "Every Sunday at 2:00 AM",
      timezone: "Amsterdam Time",
      icon: Database,
      iconColor: "text-indigo-500",
      bgColor: "bg-indigo-50 dark:bg-indigo-900/20"
    }
  ];

  return (
    <div className="flex flex-col h-full gap-6 animate-in fade-in">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-zinc-900 p-6 rounded-2xl border border-slate-200 dark:border-zinc-800 shadow-sm">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-zinc-100 flex items-center gap-2">
            <Metronome className="h-6 w-6 text-blue-500" />
            Scheduled Tasks
          </h1>
          <p className="text-sm text-slate-500 dark:text-zinc-400 mt-1">
            List of all automated background tasks executed by Google Cloud Scheduler.
          </p>
        </div>
      </div>

      {/* Task Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        {tasks.map((task, index) => (
          <div 
            key={index} 
            className="flex flex-col justify-between bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow"
          >
            <div>
              <div className="flex items-center gap-3 mb-4">
                <div className={`p-2.5 rounded-xl ${task.bgColor}`}>
                  <task.icon className={`h-5 w-5 ${task.iconColor}`} />
                </div>
                <h3 className="font-bold text-slate-900 dark:text-zinc-100">{task.title}</h3>
              </div>
              <p className="text-sm text-slate-600 dark:text-zinc-400 mb-6 leading-relaxed">
                {task.description}
              </p>
            </div>
            
            <div className="flex items-center gap-2 mt-auto pt-4 border-t border-slate-100 dark:border-zinc-800/80">
              <Clock className="h-4 w-4 text-slate-400" />
              <div className="flex flex-col">
                <span className="text-sm font-semibold text-slate-800 dark:text-zinc-200">
                  {task.schedule}
                </span>
                <span className="text-xs font-medium text-slate-500 dark:text-zinc-500 uppercase tracking-wider">
                  {task.timezone}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}