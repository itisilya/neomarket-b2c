import React, { useEffect, useState } from "react";
import { DevApiLog } from "../types";
import { Terminal, RefreshCw, Radio } from "lucide-react";

export const DevLogDashboard: React.FC = () => {
  const [logs, setLogs] = useState<DevApiLog[]>([]);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchLogs = async () => {
    try {
      const res = await fetch("/api/dev/logs");
      if (res.ok) {
        const data = await res.json();
        setLogs(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchLogs();
    let interval: any = null;
    if (autoRefresh) {
      interval = setInterval(fetchLogs, 1500);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]);

  return (
    <div id="dev-log-dashboard" className="flex flex-col gap-4 rounded-2xl border border-slate-900 bg-slate-950 p-5 font-mono text-xs text-slate-300 shadow-2xl">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <Terminal className="h-4 w-4 text-emerald-400 stroke-2" />
          <span className="font-bold tracking-tight text-white uppercase text-[11px]">B2C API Playground Activity</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-[10px] font-bold transition-all"
            style={{ color: autoRefresh ? "#10b981" : "#94a3b8" }}
          >
            <Radio className="h-3.5 w-3.5 animate-pulse" />
            {autoRefresh ? "АКТИВЕН" : "ПАУЗА"}
          </button>
          <button
            onClick={fetchLogs}
            className="rounded-lg bg-slate-800 p-1.5 text-slate-400 hover:bg-slate-700 hover:text-white transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <p className="text-[10px] text-slate-500 leading-normal mb-1">
        Логируется каждый запрос к бекенду. Нажмите на фильтры или введите запрос в строку поиска, чтобы увидеть динамические вызовы API согласно регламенту B2C-1 и B2C-2:
      </p>

      <div className="max-h-[170px] overflow-y-auto space-y-2 pr-1 select-all">
        {logs.length === 0 ? (
          <div className="text-center py-6 text-slate-600 italic">
            Ожидание запросов к API...
          </div>
        ) : (
          logs.map((log) => {
            const statusColor =
              log.status >= 400
                ? "text-rose-400 bg-rose-500/10"
                : log.status >= 300
                ? "text-amber-400 bg-amber-500/10"
                : "text-emerald-400 bg-emerald-500/10";
            return (
              <div
                key={log.id}
                className="flex items-center gap-2 rounded-lg bg-slate-900/40 p-2 border border-slate-900 transition-colors hover:bg-slate-900/80"
              >
                <span className="text-[10px] text-slate-600 shrink-0">{log.timestamp}</span>
                <span className="text-teal-400 font-bold tracking-wider shrink-0 uppercase text-[10px]">
                  {log.method}
                </span>
                <span className="truncate text-slate-300 font-semibold select-all text-[11px] flex-1">
                  {log.path}
                </span>
                <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold ${statusColor}`}>
                  {log.status}
                </span>
                <span className="text-[10px] text-slate-500 font-mono shrink-0">{log.duration}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
