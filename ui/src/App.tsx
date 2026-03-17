import { useState, useRef, useEffect } from 'react'

interface LogLine {
  text: string
  type: 'info' | 'success' | 'error' | 'warning' | 'dim'
}

function classifyLine(text: string): LogLine['type'] {
  if (text.includes('✓') || text.includes('成功') || text.includes('完成')) return 'success'
  if (text.includes('✗') || text.includes('ERROR') || text.includes('失败') || text.includes('出错')) return 'error'
  if (text.includes('WARNING') || text.includes('警告') || text.includes('跳过')) return 'warning'
  if (text.startsWith('  ')) return 'dim'
  return 'info'
}

export default function App() {
  const [logs, setLogs] = useState<LogLine[]>([])
  const [running, setRunning] = useState(false)
  const [monitorEnabled, setMonitorEnabled] = useState(false)
  const offsetRef = useRef(0)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const logEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  // 初始化时获取监控状态
  useEffect(() => {
    fetch('/api/monitor/status')
      .then(r => r.json())
      .then(d => setMonitorEnabled(d.enabled))
      .catch(() => {})
  }, [])

  const stopPolling = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }
  const startPolling = () => {
    stopPolling()
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/logs?offset=${offsetRef.current}`)
        const data = await res.json()
        if (data.logs.length > 0) {
          const newLines: LogLine[] = data.logs.map((t: string) => ({
            text: t,
            type: classifyLine(t),
          }))
          setLogs(prev => [...prev, ...newLines])
          offsetRef.current += data.logs.length
        }
        setMonitorEnabled(data.monitor_enabled)
        // 只有手动刷新结束且监控未开启时才停止轮询
        if (!data.running && !data.monitor_enabled) {
          stopPolling()
          setRunning(false)
        }
        if (!data.running) {
          setRunning(false)
        }
      } catch {
        // network hiccup, keep polling
      }
    }, 400)
  }

  const handleRefresh = async () => {
    if (running) return
    setLogs([])
    offsetRef.current = 0
    setRunning(true)
    await fetch('/api/refresh', { method: 'POST' })
    startPolling()
  }

  const toggleMonitor = async () => {
    const endpoint = monitorEnabled ? '/api/monitor/disable' : '/api/monitor/enable'
    const res = await fetch(endpoint, { method: 'POST' })
    const data = await res.json()
    setMonitorEnabled(data.enabled)
    // 开启监控后启动轮询以显示监控日志
    if (data.enabled && !pollRef.current) startPolling()
  }

  return (
    <div className="app">
      <header className="header">
        <h1>AutoDL 释放时间守护</h1>
        <span className={`badge ${running ? 'badge-running' : 'badge-idle'}`}>
          {running ? '运行中' : '空闲'}
        </span>
      </header>

      <div className="toolbar">
        <button className="btn-refresh" onClick={handleRefresh} disabled={running}>
          {running ? '⏳ 正在刷新...' : '▶ 立刻刷新所有实例'}
        </button>
        {!running && logs.length > 0 && (
          <button className="btn-clear" onClick={() => setLogs([])}>清空日志</button>
        )}
        <label className="toggle-monitor">
          <input type="checkbox" checked={monitorEnabled} onChange={toggleMonitor} />
          <span className="toggle-slider" />
          <span className="toggle-label">
            自动监控 {monitorEnabled ? '已开启' : '已关闭'}
          </span>
        </label>
      </div>

      <div className="log-area">
        {logs.length === 0 && !running && (
          <span className="placeholder">点击按钮开始刷新所有实例的释放时间...</span>
        )}
        {logs.map((line, i) => (
          <div key={i} className={`log-line log-${line.type}`}>{line.text}</div>
        ))}
        <div ref={logEndRef} />
      </div>
    </div>
  )
}
