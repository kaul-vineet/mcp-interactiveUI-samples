import { build } from 'vite';
import fs from 'fs';
import path from 'path';

const input = process.env.INPUT || 'src/hubspot/index.html';

console.log(`Building HubSpot widget from ${input}...`);
process.env.INPUT = input;
await build({ configFile: 'vite.config.ts' });

// Copy built output to ../web/widget.html (where MCP server expects it)
const builtFile = path.resolve('dist', 'src', 'hubspot', 'index.html');
const target = path.resolve('..', 'web', 'widget.html');

if (fs.existsSync(builtFile)) {
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.copyFileSync(builtFile, target);
  console.log(`  -> ${target}`);
} else {
  console.error(`Expected build output at ${builtFile} but not found.`);
  process.exit(1);
}

// Clean up nested dirs in dist
const nestedSrc = path.resolve('dist', 'src');
if (fs.existsSync(nestedSrc)) {
  fs.rmSync(nestedSrc, { recursive: true });
}
