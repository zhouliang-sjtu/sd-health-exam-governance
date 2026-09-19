// 00_link_H_checkup.js —— H社区纯体检库 7年全变量长表构建（只读原始xlsx → 单一CSV）
// 产出: data/processed/H_checkup_long.csv
const XLSX = require('xlsx');
const fs = require('fs');
const path = require('path');

const ROOT = '<institution-path>';
const OUT = path.join(ROOT, 'data/processed/H_checkup_long.csv');

const YEARS = {
  2018: '<institution-path>',
  2019: '<institution-path>',
  2020: '<institution-path>',
  2021: '<institution-path>',
  2022: '<institution-path>',
  2023: '<institution-path>',
  2024: '<institution-path>',
};

function norm(s) { return String(s == null ? '' : s).replace(/\s+/g, ''); }
function num(v) { const n = parseFloat(String(v == null ? '' : v).replace(/[,，]/g, '')); return isNaN(n) ? '' : n; }
function isID(s) { return /^(\d{17}[\dXx]|\d{15})$/.test(s); }
function cellv(ws, r, c) { const cell = ws[XLSX.utils.encode_cell({ r, c })]; return cell ? cell.v : ''; }
function birthYear(id) { const m = id.match(/^(\d{6})(\d{4})/); return m ? m[2] : ''; }

// 字段定位：按优先级正则匹配列名（norm后）
function pick(headers, patterns, excludes) {
  for (const p of patterns) {
    for (let i = 0; i < headers.length; i++) {
      const h = headers[i];
      if (!h) continue;
      if (excludes && excludes.some(x => x.test(h))) continue;
      if (p.test(h)) return i;
    }
  }
  return -1;
}

const FIELDS = [
  ['sbp',   [/^左侧收缩压/, /收缩压/],              [/右侧/]],
  ['dbp',   [/^左侧舒张压/, /舒张压/],              [/右侧/]],
  ['pulse', [/脉率/], []],
  ['hr',    [/心率/], [/心率变异/]],
  ['height',[/身高/], []],
  ['weight',[/^体重\(/, /^体重（/],                 [/指数/]],
  ['bmi',   [/体重指数/], []],
  ['waist', [/腰围/], []],
  ['wbc',   [/白细胞计数/], [/尿|CSF/]],
  ['neut',  [/中性粒细胞绝对数/, /中性粒细胞绝对值/], [/尿/]],
  ['neutP', [/中性粒细胞百分数/, /中性粒细胞百分比/], [/尿/]],
  ['lymph', [/淋巴细胞绝对数/, /淋巴细胞绝对值/],    [/尿|总T|总B|辅助|细胞毒|CSF/]],
  ['lymphP',[/淋巴细胞百分数/, /淋巴细胞百分比/],    [/尿/]],
  ['mono',  [/单核细胞绝对数/, /单核细胞绝对值/],    [/尿/]],
  ['monoP', [/单核细胞百分数/, /单核细胞百分比/],    [/尿/]],
  ['eos',   [/嗜酸性粒细胞绝对数/, /嗜酸性粒细胞绝对值/], [/尿/]],
  ['eosP',  [/嗜酸性粒细胞百分数/, /嗜酸性粒细胞百分比/], [/尿/]],
  ['baso',  [/嗜碱性粒细胞绝对数/, /嗜碱性粒细胞绝对值/], [/尿/]],
  ['basoP', [/嗜碱性粒细胞百分数/, /嗜碱性粒细胞百分比/], [/尿/]],
  ['hb',    [/^血红蛋白/], [/尿|平均/]],
  ['rbc',   [/^红细胞计数/], [/尿|CSF|网织/]],
  ['hct',   [/红细胞压积/], [/尿/]],
  ['mcv',   [/平均红细胞体积/], []],
  ['mch',   [/平均红细胞血红蛋白含量/], []],
  ['mchc',  [/平均红细胞血红蛋白浓度/], []],
  ['rdwc',  [/红细胞分布宽度-变异系数|红细胞体积分布宽度变异系数/], []],
  ['rdws',  [/红细胞分布宽度-标准差|红细胞体积分布宽度标准差/], []],
  ['plt',   [/血小板计数/], [/尿/]],
  ['mpv',   [/血小板平均体积/, /平均血小板体积/], []],
  ['pdw',   [/血小板分布宽度|血小板体积分布宽度/], []],
  ['pct',   [/血小板压积|血小板比积/], []],
  ['tbil',  [/总胆红素/], []],
  ['dbil',  [/直接胆红素/], []],
  ['alt',   [/谷丙转氨酶|丙氨酸氨基转移酶/], []],
  ['ast',   [/谷草转氨酶|天门冬氨酸氨基转氨酶/], []],
  ['bun',   [/尿素氮/], []],
  ['crea',  [/肌酐/], [/尿肌酐/]],
  ['ua',    [/^尿酸/], [/结晶|碱度/]],
  ['tc',    [/总胆固醇/], []],
  ['tg',    [/甘油三酯/], []],
  ['hdl',   [/高密度脂蛋白胆固醇/], []],
  ['ldl',   [/低密度脂蛋白胆固醇/], []],
  ['fpg',   [/空腹血糖/], []],
  ['hba1c', [/糖化血红蛋白/], []],
  ['afp',   [/甲胎蛋白/], []],
  ['cea',   [/癌胚抗原/], []],
  ['ca199', [/糖类抗原CA19-9/], []],
  ['uprot', [/^尿蛋白/, /尿蛋白质定性/], [/24小时|微量/]],
  ['uglu',  [/尿葡萄糖/], []],
  ['ubld',  [/尿潜血/], []],
  ['uket',  [/尿酮体/], []],
  ['uwbc',  [/尿白细胞/], []],
  ['unit',  [/亚硝酸盐/], []],
  ['usg',   [/比重/], []],
  ['ubg',   [/尿胆原/], []],
];

// 文本列
function pickTextCols(headers, patterns) {
  const out = [];
  headers.forEach((h, i) => { if (h && patterns.some(p => p.test(h))) out.push(i); });
  return out;
}

function parseUS(text, mainText) {
  // 脂肪肝判定：超声文本 OR 主检结果（覆盖2020年描述式写法："回声细密增强、后方衰减"）
  const t = String(text || '');
  const m2 = String(mainText || '');
  const inUS = /脂肪肝/.test(t);
  const inMain = /脂肪肝/.test(m2);
  const fatty = (inUS || inMain) ? 1 : 0;
  let degree = '';
  if (fatty) {
    const m = (t + ' ' + m2).match(/脂肪肝[^。；\n]{0,8}?(轻度|中度|重度)|((轻度|中度|重度)[^。；\n]{0,6}?脂肪肝)/);
    degree = m ? (m[1] || m[2] || '') : '';
  }
  return {
    fatty, fatty_degree: degree.replace('脂肪肝', ''),
    gallstone: /胆(囊|管)?(结石|息肉)|胆囊(结石|息肉)/.test(t) ? 1 : 0,
    kidneycyst: /肾囊肿/.test(t) ? 1 : 0,
    fibroid: /子宫肌瘤/.test(t) ? 1 : 0,
  };
}

function classifyECGv2(text) {
  const t = norm(text);
  if (t === '' || t === '×' || t === '弃检' || /拒检|图像质量差|未检/.test(t)) return null;
  const negation = /(未见|无明显|大致正常|无特殊)[^。；]{0,6}(ST|T波|异常|改变)/.test(t);
  const f = {
    af: /房颤|心房颤动|心房扑动|房扑|颤动/.test(t) && !negation ? 1 : 0,
    pacPvc: /早搏|期前收缩|过早搏动/.test(t) ? 1 : 0,
    stt: (!negation && /ST-?T|ST段|T波(改变|低平|倒置|高尖)|心肌缺血/.test(t)) ? 1 : 0,
    avblock: /房室传导阻滞|房室阻滞|一度传导|二度传导|三度传导|Ⅰ度房室|II度房室|III度房室/.test(t) ? 1 : 0,
    bbb: /束支阻滞|束支传导阻滞|分支阻滞|室内传导阻滞/.test(t) ? 1 : 0,
    rate: /心动过速|心动过缓/.test(t) ? 1 : 0,
    srirr: /窦性心律不齐|窦性不齐|窦性心动不齐|窦性心动律不齐/.test(t) ? 1 : 0,
    axis: /电轴(左|右|不)偏/.test(t) ? 1 : 0,
    rotate: /转位/.test(t) ? 1 : 0,
    lowvolt: /低电压/.test(t) ? 1 : 0,
    avdiss: /房室分离/.test(t) ? 1 : 0,
    junctional: /交界性/.test(t) ? 1 : 0,
    qwave: /异常Q波|异常q波|病理性Q波|陈旧性(下壁|前壁|侧壁|后壁)|心肌梗死|心肌梗塞/.test(t) ? 1 : 0,
    lvh: /高电压|肥大|肥厚/.test(t) ? 1 : 0,
    pacer: /起搏/.test(t) ? 1 : 0,
    prdelay: /P-?R间期(延长|延迟)|一度房室/.test(t) ? 1 : 0,
  };
  f.anyBlock = (f.avblock || f.bbb) ? 1 : 0;
  const abnMarkers = ['af','pacPvc','stt','avblock','bbb','rate','axis','rotate','lowvolt','avdiss','junctional','qwave','lvh','pacer','prdelay'];
  f.abnormal = abnMarkers.some(k => f[k]) ? 1 : 0;
  if (!f.abnormal) {
    if (/正常心电图|大致正常|未见明显异常|未见异常|正常范围|正常/.test(t)) f.normal = 1;
    else if (/窦性心律/.test(t)) f.sinusOnly = 1;
    else f.unclassified = 1;
  } else f.normal = 0;
  return f;
}

// ---------- 主流程 ----------
const HEADER = ['year','id','birth_year','sex','age','sbp','dbp','pulse','hr','height','weight','bmi','waist',
  'wbc','neut','neutP','lymph','lymphP','mono','monoP','eos','eosP','baso','basoP',
  'hb','rbc','hct','mcv','mch','mchc','rdwc','rdws','plt','mpv','pdw','pct',
  'tbil','dbil','alt','ast','bun','crea','ua','tc','tg','hdl','ldl','fpg','hba1c',
  'afp','cea','ca199','uprot','uglu','ubld','uket','uwbc','unit','usg','ubg',
  'ecg_text','ecg_abnormal','ecg_af','ecg_pacPvc','ecg_stt','ecg_anyBlock','ecg_rate','ecg_srirr','ecg_axis','ecg_qwave','ecg_normal',
  'fatty','fatty_degree','gallstone','kidneycyst','fibroid',
  'smoke','drink','chronic_mgmt_flag','past_history'];

const rows = [];
const stats = [];

for (const [year, file] of Object.entries(YEARS)) {
  process.stdout.write(`读取 ${year} ...\n`);
  const wb = XLSX.readFile(file);
  const ws = wb.Sheets[wb.SheetNames[0]];
  const range = XLSX.utils.decode_range(ws['!ref']);
  let hdrRow = -1, headers = [];
  for (let r = 0; r <= Math.min(3, range.e.r); r++) {
    const hs = []; for (let c = 0; c <= range.e.c; c++) hs.push(norm(cellv(ws, r, c)));
    if (hs.some(h => h.includes('身份证号'))) { hdrRow = r; headers = hs; break; }
  }
  if (hdrRow < 0) { stats.push({ year, error: 'no header' }); continue; }

  const colMap = {};
  for (const [name, pats, ex] of FIELDS) colMap[name] = pick(headers, pats, ex);
  const cID = headers.findIndex(h => h.includes('身份证号'));
  const cSex = headers.findIndex(h => h === '性别');
  const cAge = headers.findIndex(h => h === '年龄');
  const ecgCols = pickTextCols(headers, [/心电图/]);
  const ecgConcl = ecgCols.find(c => headers[c].includes('结论'));
  const usCols = pickTextCols(headers, [/超声检查结论/, /肝.*胆/]);
  const cMain = headers.findIndex(h => /主检结果/.test(h));
  const flagCols = pickTextCols(headers, [/主检结论|处理建议|健康建议|危险因素控制|健康指导|主检结果/]);
  const cPast = headers.findIndex(h => h.includes('既往史'));
  const cSmoke = headers.findIndex(h => h.includes('吸烟'));
  const cDrink = headers.findIndex(h => h.includes('饮酒'));

  let n = 0, nID = 0, nECG = 0, nUS = 0, fattyN = 0, dupInYear = 0;
  const seen = new Set();

  for (let r = hdrRow + 1; r <= range.e.r; r++) {
    const idRaw = norm(cellv(ws, r, cID));
    const sexRaw = norm(cellv(ws, r, cSex));
    if (idRaw === '' && sexRaw === '') continue;
    n++;
    const id = isID(idRaw) ? idRaw.toUpperCase() : '';
    if (id) { nID++; if (seen.has(id)) dupInYear++; seen.add(id); }

    const o = { year, id, birth_year: id ? birthYear(id) : '', sex: sexRaw || '', age: num(cellv(ws, r, cAge)) };
    const RAW_FIELDS = new Set(['uprot', 'uglu', 'ubld', 'uket', 'uwbc', 'unit', 'ubg']);
    for (const [name] of FIELDS) {
      const c = colMap[name];
      o[name] = c >= 0 ? (RAW_FIELDS.has(name) ? norm(cellv(ws, r, c)).slice(0, 20) : num(cellv(ws, r, c))) : '';
    }
    o.smoke = cSmoke >= 0 ? norm(cellv(ws, r, cSmoke)) : '';
    o.drink = cDrink >= 0 ? norm(cellv(ws, r, cDrink)) : '';
    o.past_history = cPast >= 0 ? norm(cellv(ws, r, cPast)).slice(0, 200) : '';

    // ECG
    let ecgText = '';
    if (ecgConcl !== undefined) ecgText = String(cellv(ws, r, ecgConcl) || '').trim();
    if (ecgText === '' || ecgText === '×' || ecgText === '弃检') {
      for (const c of ecgCols) {
        const t2 = String(cellv(ws, r, c) || '').trim();
        if (t2 !== '' && t2 !== '×' && t2 !== '弃检') { ecgText = t2; break; }
      }
    }
    o.ecg_text = ecgText.slice(0, 150);
    const f = classifyECGv2(ecgText);
    if (f) nECG++;
    o.ecg_abnormal = f ? f.abnormal : '';
    o.ecg_af = f ? f.af : ''; o.ecg_pacPvc = f ? f.pacPvc : '';
    o.ecg_stt = f ? f.stt : ''; o.ecg_anyBlock = f ? f.anyBlock : '';
    o.ecg_rate = f ? f.rate : ''; o.ecg_srirr = f ? f.srirr : '';
    o.ecg_axis = f ? (f.axis || f.rotate || f.lowvolt ? 1 : 0) : '';
    o.ecg_qwave = f ? f.qwave : ''; o.ecg_normal = f ? (f.normal || f.sinusOnly ? 1 : 0) : '';

    // US
    let usText = '';
    for (const c of usCols) { const t = String(cellv(ws, r, c) || '').trim(); if (t && t !== '×') usText += t + ' '; }
    if (usText.trim()) nUS++;
    const mainText = cMain >= 0 ? String(cellv(ws, r, cMain) || '') : '';
    const us = parseUS(usText, mainText);
    if (us.fatty) fattyN++;
    o.fatty = us.fatty; o.fatty_degree = us.fatty_degree;
    o.gallstone = us.gallstone; o.kidneycyst = us.kidneycyst; o.fibroid = us.fibroid;

    // 慢病管理标记
    let flag = 0;
    for (const c of flagCols) { if (/纳入慢性病/.test(norm(cellv(ws, r, c)))) { flag = 1; break; } }
    o.chronic_mgmt_flag = flag;

    rows.push(o);
  }
  stats.push({ year, n, validID: nID, ecgParsed: nECG, usNonEmpty: nUS, fatty: fattyN, dupInYear,
    missingCols: Object.entries(colMap).filter(([k, c]) => c < 0).map(([k]) => k) });
}

// 写CSV（同人同年重复行去重：2023年存在4,028个重复ID，保留首行）
fs.mkdirSync(path.dirname(OUT), { recursive: true });
const seenPair = new Set();
const rowsDedup = [];
let nDupDropped = 0;
for (const o of rows) {
  if (!o.id) { rowsDedup.push(o); continue; }
  const k = o.id + '|' + o.year;
  if (seenPair.has(k)) { nDupDropped++; continue; }
  seenPair.add(k);
  rowsDedup.push(o);
}
const esc = (s) => { s = String(s == null ? '' : s); return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
const lines = [HEADER.join(',')];
for (const o of rowsDedup) lines.push(HEADER.map(h => esc(o[h])).join(','));
fs.writeFileSync(OUT, '\uFEFF' + lines.join('\n'), 'utf8');

console.log('\n===== 00_link 汇总 =====');
console.log(JSON.stringify({ totalRows: rows.length, dedupDropped: nDupDropped, finalRows: rowsDedup.length, outFile: OUT, stats }, null, 1));
