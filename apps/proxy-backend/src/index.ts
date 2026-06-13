import { loadConfig } from "./config";
import { createProxyApp } from "./server";

const port = Number(Bun.env.PORT ?? "8787");
const app = createProxyApp(loadConfig());

app.listen(port);

console.log(`CodeSentinel proxy listening on http://localhost:${port}`);
