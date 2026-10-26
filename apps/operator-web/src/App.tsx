import { useEffect, useState } from 'react';

type Connection = 'checking' | 'connected' | 'disconnected';
const gateway = import.meta.env.VITE_GATEWAY_URL || 'http://localhost:8000';

export default function App() {
  const [connection, setConnection] = useState<Connection>('checking');
  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    let controller: AbortController;
    async function check() {
      controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 4000);
      try {
        const response = await fetch(`${gateway}/health`, { signal: controller.signal });
        if (!response.ok) throw new Error('Gateway unavailable');
        const body = await response.json();
        if (body.service !== 'gateway' || body.status !== 'healthy') throw new Error('Invalid health response');
        if (!disposed) setConnection('connected');
      } catch {
        if (!disposed) setConnection('disconnected');
      } finally {
        clearTimeout(timeout);
        if (!disposed) timer = setTimeout(check, 10000);
      }
    }
    void check();
    return () => { disposed = true; clearTimeout(timer); controller?.abort(); };
  }, []);

  return (
    <main>
      <header><p className="eyebrow">LOCAL DEVELOPMENT · PHASE 1</p><h1>Support Operator Console</h1>
        <p className={`connection ${connection}`} role="status">Gateway: {connection}</p>
      </header>
      <section aria-labelledby="section-title">
        <h2 id="section-title">Pending approvals</h2>
        <div className="placeholder"><span aria-hidden="true">◇</span><p>The approval workflow will be added in a later phase.</p></div>
        <p className="note">Approval requests will appear here when the workflow is available.</p>
      </section>
      <footer>Infrastructure is ready for the next chapter.</footer>
    </main>
  );
}
