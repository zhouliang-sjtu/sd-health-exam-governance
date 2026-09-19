// B36c_chain_verify.js —— 2023 结论列串扰链取证：心电图结论=尿检 的行，其放射科列是否为对应心电文本
const XLSX = require('<institution-path>');
const fs = require('fs');
const norm = s => String(s == null ? '' : s).replace(/\s+/g, '');
const cellv = (ws, r, c) => { const cell = ws[XLSX.utils.encode_cell({ r, c })]; return cell ? cell.v : ''; };
const CLAUSE = /^尿(潜血|白细胞|葡萄糖|蛋白|酮体|胆原|维C|亚硝酸盐|比重|酸碱度)|^亚硝酸盐/;
const isUrine = t => { const s = String(t||'').trim(); if (!s) return false;
  const segs = s.split(/[；;]/).map(x=>x.trim()).filter(Boolean);
  return segs.every(x => CLAUSE.test(x) || /^尿潜血\+?\d*。?$/.test(x)); };
const ECGTXT = /窦性|心电图|ST段|ST-?T|T波|房颤|房扑|传导阻滞|早搏|电轴|Q波|期前收缩/;

const wb = XLSX.readFile('<institution-path>');
const ws = wb.Sheets[wb.SheetNames[0]];
const range = XLSX.utils.decode_range(ws['!ref']);
let hdrRow = -1, headers = [];
for (let r = 0; r <= Math.min(3, range.e.r); r++) {
  const hs = []; for (let c = 0; c <= range.e.c; c++) hs.push(norm(cellv(ws, r, c)));
  if (hs.some(h => h.includes('身份证号'))) { hdrRow = r; headers = hs; break; }
}
const cECG = headers.findIndex(h => h.includes('心电图') && h.includes('结论'));
const cRad = headers.findIndex(h => h === '放射科结论');
const cUrine = headers.findIndex(h => h.includes('尿常规') && h.includes('结论'));
const cCT = headers.findIndex(h => h.includes('CT') && h.includes('结论'));
const cYou = headers.findIndex(h => h === '优生优育结论');
const cX = headers.findIndex(h => h === '胸部X线检查结论');
console.error('cols:', {cECG, cRad, cUrine, cCT, cYou, cX});

let nUrineECG = 0, radIsECG = 0, radEmpty = 0, radOther = 0, urineColOK = 0;
let radSamples = [];
for (let r = hdrRow + 1; r <= range.e.r; r++) {
  const tE = String(cellv(ws, r, cECG) || '').trim();
  if (!isUrine(tE)) continue;
  nUrineECG++;
  const tR = String(cellv(ws, r, cRad) || '').trim();
  if (!tR) radEmpty++;
  else if (ECGTXT.test(tR)) { radIsECG++; if (radSamples.length < 5) radSamples.push(tR.slice(0, 50)); }
  else radOther++;
  const tU = String(cellv(ws, r, cUrine) || '').trim();
  if (tU) urineColOK++;
}
// 反向：放射科列含心电文本的行，其心电图结论列是什么
let nRadECG = 0, ecgColUrine = 0, ecgColECG = 0, ecgColEmpty = 0, ecgColOther = 0;
for (let r = hdrRow + 1; r <= range.e.r; r++) {
  const tR = String(cellv(ws, r, cRad) || '').trim();
  if (!tR || !ECGTXT.test(tR)) continue;
  nRadECG++;
  const tE = String(cellv(ws, r, cECG) || '').trim();
  if (isUrine(tE)) ecgColUrine++;
  else if (ECGTXT.test(tE) || /正常心电图|大致正常/.test(tE)) ecgColECG++;
  else if (!tE) ecgColEmpty++;
  else ecgColOther++;
}
const res = { nUrineECG, radIsECG, radEmpty, radOther, urineColOK, radSamples,
  nRadECG, ecgColUrine, ecgColECG, ecgColEmpty, ecgColOther };
fs.writeFileSync('<institution-path>', JSON.stringify(res, null, 1), 'utf8');
console.log(JSON.stringify(res, null, 1));
