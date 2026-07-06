import { HatGlasses, Shield } from "lucide-react";

export default function Login() {
  // Read dynamically from the Vite environment
  const GITHUB_CLIENT_ID = import.meta.env.VITE_GITHUB_CLIENT_ID;
  
  const handleLogin = () => {
    window.location.href = `https://github.com/login/oauth/authorize?client_id=${GITHUB_CLIENT_ID}&scope=user:email`;
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-slate-50 dark:bg-slate-950">

      <div className="relative z-10 w-full max-w-md p-8 bg-white/70 dark:bg-slate-900/70 backdrop-blur-xl border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl">
        <div className="flex flex-col items-center mb-8">
          <div className="p-3 bg-blue-500 text-white rounded-xl mb-4 shadow-lg shadow-blue-500/30">
            <Shield size={32} />
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Isha Core</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-2 text-center">
            Strategic Pentest Planning & Asset Management
          </p>
        </div>

        <button
          onClick={handleLogin}
          className="w-full flex items-center justify-center gap-3 bg-slate-900 dark:bg-white text-white dark:text-slate-900 px-6 py-3 rounded-lg font-medium hover:bg-slate-800 dark:hover:bg-slate-100 transition-all active:scale-95"
        >
          <HatGlasses size={20} />
          Continue with GitHub
        </button>
      </div>
    </div>
  );
}