import { useEffect, useState } from "react";

interface HealthStatus {
  status: string;
  database: string;
}

function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((res) => res.json())
      .then((data: HealthStatus) => setHealth(data))
      .catch(() => setError("Could not connect to backend"));
  }, []);

  const isHealthy = health?.status === "healthy";
  const statusColor = isHealthy ? "#22c55e" : "#ef4444";

  return (
    <div style={{ fontFamily: "system-ui, sans-serif", padding: "2rem" }}>
      <h1>Fantasy Manager</h1>
      {error && <p style={{ color: "#ef4444" }}>{error}</p>}
      {health && (
        <p style={{ color: statusColor }}>
          Backend: {health.status} | DB: {health.database}
        </p>
      )}
      {!health && !error && <p>Connecting to backend...</p>}
    </div>
  );
}

export default App;
