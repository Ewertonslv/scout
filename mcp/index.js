#!/usr/bin/env node
// scout-mcp — exposes the deployed scout pipeline as an MCP tool, so any MCP
// client (Claude Desktop, IDEs) can call `research(topic)` and get a cited brief.
//
// This is scout's differentiator: the same AWS multi-agent backend is reachable
// both as an HTTP API and over the Model Context Protocol.
//
// Configure the target with the SCOUT_API_BASE env var, e.g.
//   SCOUT_API_BASE="https://xxxx.execute-api.us-east-1.amazonaws.com" npx scout-mcp

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const API_BASE = process.env.SCOUT_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";
const POLL_INTERVAL_MS = 1500;
const MAX_POLLS = 60;

async function research(topic, quality) {
  const submit = await fetch(`${API_BASE}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, quality }),
  });
  if (submit.status === 429) throw new Error("daily run limit reached");
  if (!submit.ok) throw new Error(`submit failed: HTTP ${submit.status}`);

  const body = await submit.json();
  if (body.brief) return body.brief.markdown; // synchronous (local) path

  const jobId = body.job_id;
  for (let i = 0; i < MAX_POLLS; i++) {
    const r = await fetch(`${API_BASE}/jobs/${jobId}`);
    const job = await r.json();
    if (job.status === "DONE") return job.brief.markdown;
    if (job.status === "FAILED") throw new Error(job.error || "pipeline failed");
    await new Promise((res) => setTimeout(res, POLL_INTERVAL_MS));
  }
  throw new Error("timed out waiting for brief");
}

const server = new McpServer({ name: "scout", version: "0.1.0" });

server.tool(
  "research",
  "Run a multi-agent research pipeline on AWS and return a cited markdown brief on the given topic.",
  {
    topic: z.string().min(3).describe("The topic or question to research"),
    quality: z.boolean().optional().describe("Use the higher-quality (Claude) model"),
  },
  async ({ topic, quality }) => {
    const markdown = await research(topic, quality ?? false);
    return { content: [{ type: "text", text: markdown }] };
  },
);

await server.connect(new StdioServerTransport());
