// Check what licence notices survive in frontend/dist: legal comments in the JS bundle and the OFL notice inside
// each shipped WOFF2 font (name table, decoded with Node's built-in brotli). Read-only.
//   node dist_notices.mjs <distDir> <out.json>
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";

const [dist, outFile] = process.argv.slice(2).map((p) => path.resolve(p));
const assets = path.join(dist, "assets");
const out = { js: [], fonts: [] };

for (const f of fs.readdirSync(assets).filter((f) => f.endsWith(".js"))) {
  const s = fs.readFileSync(path.join(assets, f), "utf8");
  const comments = [...s.matchAll(/\/\*[!*][\s\S]*?\*\//g)].map((m) => m[0]).filter((c) => /licen[cs]e|copyright|@preserve/i.test(c));
  out.js.push({ file: f, bytes: s.length, legal_comments: comments.length,
    comments: comments.map((c) => c.replace(/\s+/g, " ").slice(0, 240)) });
}

const readBase128 = (b, o) => { let v = 0; for (let i = 0; i < 5; i++) { const x = b[o.p++]; v = (v << 7) | (x & 0x7f); if (!(x & 0x80)) return v; } throw new Error("bad UIntBase128"); };
const TAGS = ["cmap","head","hhea","hmtx","maxp","name","OS/2","post","cvt ","fpgm","glyf","loca","prep","CFF ","VORG","EBDT","EBLC","gasp","hdmx","kern","LTSH","PCLT","VDMX","vhea","vmtx","BASE","GDEF","GPOS","GSUB","EBSC","JSTF","MATH","CBDT","CBLC","COLR","CPAL","SVG ","sbix","acnt","avar","bdat","bloc","bsln","cvar","fdsc","feat","fmtx","fvar","gvar","hsty","just","lcar","mort","morx","opbd","prop","trak","Zapf","Silf","Glat","Gloc","Feat","Sill"];
for (const f of fs.readdirSync(assets).filter((f) => f.endsWith(".woff2"))) {
  const b = fs.readFileSync(path.join(assets, f));
  const rec = { file: f, bytes: b.length };
  try {
    if (b.toString("latin1", 0, 4) !== "wOF2") throw new Error("not WOFF2");
    const numTables = b.readUInt16BE(12), compLen = b.readUInt32BE(20), metaOffset = b.readUInt32BE(28), metaLength = b.readUInt32BE(32);
    const o = { p: 48 }, tables = [];
    for (let i = 0; i < numTables; i++) {
      const flags = b[o.p++];
      const tag = (flags & 63) === 63 ? b.toString("latin1", o.p, (o.p += 4)) : TAGS[flags & 63];
      const orig = readBase128(b, o);
      const xf = (flags >> 6) & 3;
      const transformed = (tag === "glyf" || tag === "loca") ? xf === 0 : xf !== 0;
      const len = transformed ? readBase128(b, o) : orig;
      tables.push({ tag, len });
    }
    const data = zlib.brotliDecompressSync(b.subarray(o.p, o.p + compLen));
    let off = 0; let name = null;
    for (const t of tables) { if (t.tag === "name") name = data.subarray(off, off + t.len); off += t.len; }
    const records = [];
    if (name) {
      const count = name.readUInt16BE(2), strOff = name.readUInt16BE(4);
      for (let i = 0; i < count; i++) {
        const r = 6 + i * 12;
        const plat = name.readUInt16BE(r), nameId = name.readUInt16BE(r + 6), len = name.readUInt16BE(r + 8), so = name.readUInt16BE(r + 10);
        const raw = name.subarray(strOff + so, strOff + so + len);
        const text = plat === 3 || plat === 0 ? Buffer.from(raw).swap16().toString("utf16le") : raw.toString("latin1");
        if ([0, 1, 5, 7, 8, 9, 11, 13, 14].includes(nameId) && (plat === 3 || plat === 0)) records.push({ nameId, text: text.slice(0, 400) });
      }
    }
    rec.tables = tables.map((t) => t.tag);
    rec.extended_metadata = metaLength > 0 ? { offset: metaOffset, length: metaLength } : null;
    rec.name_records = [...new Map(records.map((r) => [r.nameId, r])).values()];
    rec.copyright = rec.name_records.find((r) => r.nameId === 0)?.text ?? null;
    rec.license_description = rec.name_records.find((r) => r.nameId === 13)?.text ?? null;
    rec.license_url = rec.name_records.find((r) => r.nameId === 14)?.text ?? null;
  } catch (e) { rec.error = String(e.message || e); }
  out.fonts.push(rec);
}
out.other_files = fs.readdirSync(dist, { recursive: true }).map(String).filter((f) => /licen|notice|copying/i.test(f));
fs.writeFileSync(outFile, JSON.stringify(out, null, 1));
for (const j of out.js) console.log(`JS ${j.file}: ${j.legal_comments} legal comments`, j.comments.map((c) => c.slice(0, 100)));
for (const ft of out.fonts) console.log(`FONT ${ft.file}: copyright=${JSON.stringify(ft.copyright)} licenseDesc=${JSON.stringify(ft.license_description?.slice(0, 120))} url=${ft.license_url} ${ft.error ?? ""}`);
console.log("licence files in dist:", out.other_files);
