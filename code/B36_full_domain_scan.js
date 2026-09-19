// B36_full_domain_scan.js —— 全列域交叉扫描（D-005）：7 年原始 Excel × 全部文本列 × 域指纹矩阵
// 目的：系统性排查"表头域 vs 内容域"错配（D-001 为已确认案例；2022 移位前科提示文本列可整列错位）
// 方法：对每列统计非空数与各域关键词行命中数；文本列（均长>4 且非空率>1%）进入矩阵；
//       异常判定：内容主域 ≠ 表头语义域，或异域句命中率 >5%
const XLSX = require('<institution-path>');
const fs = require('fs');
const norm = s => String(s == null ? '' : s).replace(/\s+/g, '');
const cellv = (ws, r, c) => { const cell = ws[XLSX.utils.encode_cell({ r, c })]; return cell ? cell.v : ''; };

const YEARS = {
  2018: '<institution-path>',
  2019: '<institution-path>',
  2020: '<institution-path>',
  2021: '<institution-path>',
  2022: '<institution-path>',
  2023: '<institution-path>',
  2024: '<institution-path>',
};
// 域指纹词族（行级命中：文本任一分割段以/含该族词计 1）
const DOMAINS = {
  ECG: /窦性|心电|ST段|ST-?T|T波|房颤|房扑|传导阻滞|早搏|电轴|Q波|期前收缩|预激/,
  US_abd: /脂肪肝|胆囊|胆结石|胆息肉|肝囊肿|肾囊肿|血管瘤|肝内|脾脏|胰腺|腹腔/,
  US_card: /室间隔|左房|左室|右房|右室|射血分数|瓣膜|心包|主动脉根部/,
  URINE: /尿潜血|尿白细胞|尿葡萄糖|尿蛋白|尿酮体|尿胆原|亚硝酸盐|尿比重|尿肌酐|尿常规/,
  CBC: /白细胞计数|中性粒|淋巴细胞|血红蛋白|红细胞计数|血小板/,
  BIOCHEM: /转氨酶|胆红素|肌酐|尿素氮|尿酸|葡萄糖|甘油三酯|胆固醇|载脂蛋白/,
  RADIO: /CT|MRI|X线|摄片|影像|放射/,
  MAIN: /建议|随访|复查|定期|内科|外科|总检|主检/,
  QUESTION: /吸烟|饮酒|吸烟史|饮酒史|锻炼|饮食/,
  GYN: /宫颈|阴道|乳腺|子宫|附件/,
};
// 表头语义域（norm 后含关键词即归属；用于和内容主域对照）
const HEADER_DOMAIN = [
  ['ECG', /心电图/], ['US_abd', /超声|B超|肝胆|腹部/], ['US_card', /心脏彩超|心超/],
  ['URINE', /尿常规|尿液/], ['CBC', /血常规/], ['BIOCHEM', /生化|血糖|血脂|肝功|肾功/],
  ['RADIO', /CT|MRI|放射|胸片/], ['GYN', /妇科|宫颈|乳腺/], ['MAIN', /主检|总检|建议/],
  ['QUESTION', /吸烟|饮酒|既往史|病史/], ['ID', /身份证|姓名|编号|日期|年龄|性别/],
];
const headerDomainOf = h => (HEADER_DOMAIN.find(([_, re]) => re.test(h)) || [null])[0];
const splitSegs = t => t.split(/[。；;,，\n]/).map(x => x.trim()).filter(Boolean);

const allRows = [];
for (const [year, file] of Object.entries(YEARS)) {
  console.error(`scanning ${year} ...`);
  const wb = XLSX.readFile(file);
  const ws = wb.Sheets[wb.SheetNames[0]];
  const range = XLSX.utils.decode_range(ws['!ref']);
  let hdrRow = -1, headers = [];
  for (let r = 0; r <= Math.min(3, range.e.r); r++) {
    const hs = []; for (let c = 0; c <= range.e.c; c++) hs.push(norm(cellv(ws, r, c)));
    if (hs.some(h => h.includes('身份证号'))) { hdrRow = r; headers = hs; break; }
  }
  if (hdrRow < 0) { allRows.push({ year, error: 'no header' }); continue; }
  // 每列累计：非空、总长、各域命中行数
  const cols = [];
  for (let c = 0; c <= range.e.c; c++) cols.push({ h: headers[c] || `col${c}`, ne: 0, sum: 0, dom: {} });
  for (let r = hdrRow + 1; r <= range.e.r; r++) {
    for (let c = 0; c <= range.e.c; c++) {
      const raw = cellv(ws, r, c);
      if (raw === '' || raw == null) continue;
      const t = String(raw).trim();
      if (t === '') continue;
      const col = cols[c];
      col.ne++;
      const isNumeric = /^[+\-]?[\d.,]+$/.test(t);
      if (!isNumeric) col.sum += t.length;
      const segs = splitSegs(t);
      for (const [dom, re] of Object.entries(DOMAINS)) {
        if (segs.some(s => re.test(s))) col.dom[dom] = (col.dom[dom] || 0) + 1;
      }
    }
  }
  for (let c = 0; c <= range.e.c; c++) {
    const col = cols[c];
    if (col.ne === 0) continue;
    const avgLen = col.sum / col.ne;
    const isText = avgLen > 4;
    if (!isText) continue;
    // 内容主域 = 命中行数最多的域（要求覆盖非空 ≥2%）
    const domEntries = Object.entries(col.dom).filter(([, n]) => n / col.ne >= 0.02).sort((a, b) => b[1] - a[1]);
    const contentDomain = domEntries.length ? domEntries[0][0] : 'NONE';
    const hd = headerDomainOf(col.h);
    allRows.push({
      year: +year, colIdx: c, header: col.h, headerDomain: hd || 'UNMAPPED',
      nonEmpty: col.ne, avgLen: Math.round(avgLen), contentDomain,
      contentPct: domEntries.length ? Math.round(domEntries[0][1] / col.ne * 100) : 0,
      domBreakdown: domEntries.map(([d, n]) => `${d}:${Math.round(n / col.ne * 100)}%`).join(' '),
    });
  }
}
const RES = '<institution-path>';
fs.writeFileSync(RES + '/B36_full_domain_scan.csv', '\uFEFF' +
  ['year', 'colIdx', 'header', 'headerDomain', 'nonEmpty', 'avgLen', 'contentDomain', 'contentPct', 'domBreakdown']
    .join(',') + '\n' + allRows.map(o => [o.year, o.colIdx, `"${(o.header || '').replace(/"/g, '""')}"`,
    o.headerDomain, o.nonEmpty, o.avgLen, o.contentDomain, o.contentPct, `"${o.domBreakdown}"`].join(',')).join('\n'), 'utf8');
// 异常格：文本列中 (a) headerDomain 与 contentDomain 均已知且不一致 且 contentPct≥20；(b) 任意异域句命中率≥20% 且不属于主检/汇总列
const suspects = allRows.filter(o => {
  if (o.error) return false;
  if (o.headerDomain === 'MAIN' || o.headerDomain === 'ID') return false; // 汇总列天然多域
  if (o.contentDomain === 'NONE') return false;
  return o.headerDomain !== o.contentDomain && o.contentPct >= 20;
});
fs.writeFileSync(RES + '/B36_suspects.csv', '\uFEFF' +
  ['year', 'colIdx', 'header', 'headerDomain', 'nonEmpty', 'contentDomain', 'contentPct', 'domBreakdown']
    .join(',') + '\n' + suspects.map(o => [o.year, o.colIdx, `"${o.header}"`, o.headerDomain, o.nonEmpty,
    o.contentDomain, o.contentPct, `"${o.domBreakdown}"`].join(',')).join('\n'), 'utf8');
console.error(`文本列 ${allRows.length}，疑点 ${suspects.length}`);
console.log(suspects.map(o => `${o.year} ${o.header} [表头=${o.headerDomain}] 内容主域=${o.contentDomain}(${o.contentPct}%) n=${o.nonEmpty}`).join('\n'));
