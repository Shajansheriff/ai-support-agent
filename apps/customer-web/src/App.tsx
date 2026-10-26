import { useEffect, useState } from 'react';

type Connection = 'checking' | 'connected' | 'disconnected';
const backend = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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
        const response = await fetch(`${backend}/health`, { signal: controller.signal });
        if (!response.ok) throw new Error('Backend unavailable');
        const body = await response.json();
        if (body.service !== 'backend' || body.status !== 'healthy') throw new Error('Invalid health response');
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
      <header><p className="eyebrow">LOCAL DEVELOPMENT · PHASE 1</p><h1>AI Store Support</h1>
        <p className={`connection ${connection}`} role="status">Backend: {connection}</p>
      </header>
      <section aria-labelledby="section-title">
        <h2 id="section-title">Your support conversation</h2>
        <div className="placeholder"><span aria-hidden="true">◇</span><p>Chat functionality will be added in a later phase.</p></div>
        <label htmlFor="message">Message</label><div className="composer"><input id="message" placeholder="Chat coming soon" disabled /><button disabled>Send</button></div>
      </section>
      <footer>Infrastructure is ready for the next chapter.</footer>
    </main>
  );
}
