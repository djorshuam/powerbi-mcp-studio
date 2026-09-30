#!/usr/bin/env node
// Instala a skill powerbi-mcp-studio no Claude Code.
//   npx github:djorshuam/powerbi-mcp-studio            -> ~/.claude (todas as sessoes)
//   npx github:djorshuam/powerbi-mcp-studio --projeto  -> ./.claude (so este projeto)
//   ... --zip                                           -> gera powerbi-mcp-studio.zip para enviar no app Claude
//   ... --desinstalar
const fs = require("fs"), path = require("path"), os = require("os");
const raiz = path.join(__dirname, "..");
const args = process.argv.slice(2);
const destino = args.includes("--projeto") ? path.join(process.cwd(), ".claude") : path.join(os.homedir(), ".claude");
const skill = path.join(destino, "skills", "powerbi-mcp-studio");
const agentes = fs.readdirSync(path.join(raiz, "agents")).filter(f => f.endsWith(".md"));

if (args.includes("--desinstalar")) {
  fs.rmSync(skill, { recursive: true, force: true });
  agentes.forEach(a => fs.rmSync(path.join(destino, "agents", a), { force: true }));
  console.log("powerbi-mcp-studio removida de " + destino);
  process.exit(0);
}
if (args.includes("--zip")) {
  const { execSync } = require("child_process");
  const saida = path.join(process.cwd(), "powerbi-mcp-studio.zip");
  const cwd = path.join(raiz, "skills");
  try {
    if (process.platform === "win32")
      execSync(`powershell -NoProfile -Command "Compress-Archive -Force -Path 'powerbi-mcp-studio' -DestinationPath '${saida}'"`, { cwd, stdio: "inherit" });
    else execSync(`zip -qr "${saida}" powerbi-mcp-studio`, { cwd, stdio: "inherit" });
    console.log("Gerado: " + saida + "  (Claude app: Configuracoes > Capacidades > Skills > enviar)");
  } catch (e) { console.error("Falha ao compactar: " + e.message); process.exit(1); }
  process.exit(0);
}
fs.cpSync(path.join(raiz, "skills", "powerbi-mcp-studio"), skill, { recursive: true, force: true });
fs.mkdirSync(path.join(destino, "agents"), { recursive: true });
agentes.forEach(a => fs.copyFileSync(path.join(raiz, "agents", a), path.join(destino, "agents", a)));
console.log(`\n  powerbi-mcp-studio instalada em ${skill}`);
console.log(`  ${agentes.length} agentes em ${path.join(destino, "agents")}\n`);
console.log("  Proximos passos:");
console.log("  1. MCP do Power BI:  claude mcp add powerbi-modeling --scope user -- npx -y @microsoft/powerbi-modeling-mcp@latest --start --readwrite --require-confirmation");
console.log("  2. Python 3.9+ na maquina");
console.log("  3. Abra o Claude Code e peca: \"transforma essa planilha num dashboard no Power BI\"\n");
